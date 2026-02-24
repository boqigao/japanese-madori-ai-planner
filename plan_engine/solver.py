from __future__ import annotations

import math
from dataclasses import dataclass

from ortools.sat.python import cp_model

from .constants import (
    MAJOR_ROOM_TYPES,
    WET_MODULE_SIZES_MM,
    WET_SPACE_TYPES,
    ceil_to_grid,
    cells_to_mm,
    mm_to_cells,
    tatami_to_cells,
)
from .models import (
    FloorSolution,
    PlanSolution,
    PlanSpec,
    Rect,
    SpaceGeometry,
    SpaceSpec,
    StairGeometry,
    StairSpec,
)


@dataclass
class RectVar:
    x: cp_model.IntVar
    y: cp_model.IntVar
    w: cp_model.IntVar
    h: cp_model.IntVar
    x_end: cp_model.IntVar
    y_end: cp_model.IntVar
    area: cp_model.IntVar
    x_interval: cp_model.IntervalVar
    y_interval: cp_model.IntervalVar


@dataclass(frozen=True)
class StairFootprint:
    w_cells: int
    h_cells: int
    components: list[tuple[str, int, int, int, int]]
    riser_count: int
    tread_count: int
    landing_mm: tuple[int, int]


DEFAULT_MIN_TATAMI: dict[str, float] = {
    "entry": 2.0,
    "hall": 2.0,
    "ldk": 12.0,
    "bedroom": 6.0,
}


class PlanSolver:
    def __init__(self, max_time_seconds: float = 20.0, num_workers: int = 8) -> None:
        self.max_time_seconds = max_time_seconds
        self.num_workers = num_workers

    def solve(self, spec: PlanSpec) -> PlanSolution:
        envelope_w_cells = mm_to_cells(spec.site.envelope.width, spec.grid.minor)
        envelope_h_cells = mm_to_cells(spec.site.envelope.depth, spec.grid.minor)
        max_area = envelope_w_cells * envelope_h_cells

        model = cp_model.CpModel()

        placements: dict[str, dict[str, list[RectVar]]] = {fid: {} for fid in spec.floors}
        target_shortfalls: list[tuple[cp_model.IntVar, int]] = []
        target_overshoots: list[tuple[cp_model.IntVar, int]] = []
        major_room_alignment_penalties: list[cp_model.IntVar] = []
        shape_balance_penalties: list[cp_model.IntVar] = []
        hall_area_penalties: list[cp_model.IntVar] = []
        floor_compactness_terms: list[cp_model.IntVar] = []

        stair_spec = _find_global_stair(spec)
        stair_footprint: StairFootprint | None = None
        stair_x: cp_model.IntVar | None = None
        stair_y: cp_model.IntVar | None = None
        floors_with_stair: set[str] = set()
        floor_area_vars: dict[str, list[cp_model.IntVar]] = {fid: [] for fid in spec.floors}
        if stair_spec is not None:
            stair_footprint = _compute_stair_footprint(stair_spec, spec.grid.minor)
            stair_x = model.NewIntVar(
                0,
                envelope_w_cells - stair_footprint.w_cells,
                f"{_slug(stair_spec.id)}_x",
            )
            stair_y = model.NewIntVar(
                0,
                envelope_h_cells - stair_footprint.h_cells,
                f"{_slug(stair_spec.id)}_y",
            )
            floors_with_stair = set(stair_spec.connects.keys())
            floors_with_stair.update(
                floor_id for floor_id, floor in spec.floors.items() if floor.core.stair is not None
            )
            floors_with_stair.intersection_update(spec.floors.keys())

        for floor_id, floor in spec.floors.items():
            for space in floor.spaces:
                component_count = _component_count(space)
                fixed_dims = WET_MODULE_SIZES_MM.get(space.type)
                if fixed_dims is not None and component_count != 1:
                    raise ValueError(f"wet module '{space.id}' must be one rectangle")

                rects: list[RectVar] = []
                for index in range(component_count):
                    prefix = f"{_slug(floor_id)}_{_slug(space.id)}_{index}"
                    fixed_w_cells = None
                    fixed_h_cells = None
                    if fixed_dims is not None:
                        fixed_w_cells = mm_to_cells(fixed_dims[0], spec.grid.minor)
                        fixed_h_cells = mm_to_cells(fixed_dims[1], spec.grid.minor)
                    rect = self._new_rect(
                        model=model,
                        prefix=prefix,
                        max_w=envelope_w_cells,
                        max_h=envelope_h_cells,
                        fixed_w=fixed_w_cells,
                        fixed_h=fixed_h_cells,
                    )
                    rects.append(rect)

                placements[floor_id][space.id] = rects

                min_width_cells = _min_width_cells(space, spec.grid.minor)
                for idx, rect in enumerate(rects):
                    min_dim = model.NewIntVar(
                        1,
                        max(envelope_w_cells, envelope_h_cells),
                        f"{_slug(floor_id)}_{_slug(space.id)}_{idx}_min_dim",
                    )
                    model.AddMinEquality(min_dim, [rect.w, rect.h])
                    model.Add(min_dim >= min_width_cells)
                    if space.type == "hall":
                        max_hall_width_cells = mm_to_cells(1820, spec.grid.minor)
                        model.Add(min_dim <= max_hall_width_cells)

                area_sum = model.NewIntVar(
                    1,
                    max_area * component_count,
                    f"{_slug(floor_id)}_{_slug(space.id)}_area_sum",
                )
                model.Add(area_sum == sum(r.area for r in rects))

                min_area_cells = _min_area_cells(space, spec.grid.minor)
                model.Add(area_sum >= min_area_cells)
                if space.type == "hall":
                    hall_area_penalties.append(area_sum)

                target_area_cells = _target_area_cells(space, spec.grid.minor)
                if target_area_cells is not None:
                    shortfall = model.NewIntVar(
                        0,
                        max_area * component_count,
                        f"{_slug(floor_id)}_{_slug(space.id)}_area_shortfall",
                    )
                    model.Add(shortfall >= target_area_cells - area_sum)
                    target_shortfalls.append((shortfall, _shortfall_weight(space.type)))
                    overshoot = model.NewIntVar(
                        0,
                        max_area * component_count,
                        f"{_slug(floor_id)}_{_slug(space.id)}_area_overshoot",
                    )
                    model.Add(overshoot >= area_sum - target_area_cells)
                    target_overshoots.append((overshoot, _overshoot_weight(space.type)))

                max_area_cells = _max_area_cells(space, spec.grid.minor)
                if max_area_cells is not None:
                    model.Add(area_sum <= max_area_cells)

                floor_area_vars[floor_id].append(area_sum)

                if component_count == 2:
                    self._touching_constraint(
                        model=model,
                        rects_a=[rects[0]],
                        rects_b=[rects[1]],
                        max_w=envelope_w_cells,
                        max_h=envelope_h_cells,
                        prefix=f"{_slug(floor_id)}_{_slug(space.id)}_l2",
                        required=True,
                    )

                if space.type in MAJOR_ROOM_TYPES:
                    for idx, rect in enumerate(rects):
                        odd_w = model.NewIntVar(0, 1, f"{_slug(floor_id)}_{_slug(space.id)}_{idx}_odd_w")
                        odd_h = model.NewIntVar(0, 1, f"{_slug(floor_id)}_{_slug(space.id)}_{idx}_odd_h")
                        model.AddModuloEquality(odd_w, rect.w, 2)
                        model.AddModuloEquality(odd_h, rect.h, 2)
                        major_room_alignment_penalties.extend([odd_w, odd_h])

                if space.type not in {"hall", "toilet", "wc", "washroom", "bath"}:
                    for idx, rect in enumerate(rects):
                        model.Add(rect.w <= 5 * rect.h)
                        model.Add(rect.h <= 5 * rect.w)
                        aspect_delta = model.NewIntVar(
                            0,
                            max(envelope_w_cells, envelope_h_cells),
                            f"{_slug(floor_id)}_{_slug(space.id)}_{idx}_aspect_delta",
                        )
                        model.Add(aspect_delta >= rect.w - rect.h)
                        model.Add(aspect_delta >= rect.h - rect.w)
                        shape_balance_penalties.append(aspect_delta)

            if stair_spec is not None and floor_id in floors_with_stair and stair_footprint is not None:
                stair_rects: list[RectVar] = []
                for component_name, dx, dy, comp_w, comp_h in stair_footprint.components:
                    stair_rect = self._new_rect(
                        model=model,
                        prefix=f"{_slug(floor_id)}_{_slug(stair_spec.id)}_{_slug(component_name)}",
                        max_w=envelope_w_cells,
                        max_h=envelope_h_cells,
                        fixed_w=comp_w,
                        fixed_h=comp_h,
                        shared_x=stair_x,
                        shared_y=stair_y,
                        shared_x_offset=dx,
                        shared_y_offset=dy,
                    )
                    stair_rects.append(stair_rect)
                    floor_area_vars[floor_id].append(stair_rect.area)
                placements[floor_id][stair_spec.id] = stair_rects

        for floor_id, entities in placements.items():
            all_rects = [rect for rects in entities.values() for rect in rects]
            if all_rects:
                model.AddNoOverlap2D(
                    [r.x_interval for r in all_rects],
                    [r.y_interval for r in all_rects],
                )

                min_x = model.NewIntVar(0, envelope_w_cells, f"{_slug(floor_id)}_min_x")
                min_y = model.NewIntVar(0, envelope_h_cells, f"{_slug(floor_id)}_min_y")
                max_x = model.NewIntVar(0, envelope_w_cells, f"{_slug(floor_id)}_max_x")
                max_y = model.NewIntVar(0, envelope_h_cells, f"{_slug(floor_id)}_max_y")
                model.AddMinEquality(min_x, [rect.x for rect in all_rects])
                model.AddMinEquality(min_y, [rect.y for rect in all_rects])
                model.AddMaxEquality(max_x, [rect.x_end for rect in all_rects])
                model.AddMaxEquality(max_y, [rect.y_end for rect in all_rects])

                span_x = model.NewIntVar(1, envelope_w_cells, f"{_slug(floor_id)}_span_x")
                span_y = model.NewIntVar(1, envelope_h_cells, f"{_slug(floor_id)}_span_y")
                model.Add(span_x == max_x - min_x)
                model.Add(span_y == max_y - min_y)
                floor_compactness_terms.extend([span_x, span_y])

                used_area = model.NewIntVar(0, max_area, f"{_slug(floor_id)}_used_area")
                model.Add(used_area == sum(floor_area_vars[floor_id]))
                model.Add(used_area == max_area)

        for floor_id, floor in spec.floors.items():
            for left_id, right_id in floor.topology.adjacency:
                if left_id not in placements[floor_id]:
                    raise ValueError(f"unknown topology id '{left_id}' in floor {floor_id}")
                if right_id not in placements[floor_id]:
                    raise ValueError(f"unknown topology id '{right_id}' in floor {floor_id}")
                self._touching_constraint(
                    model=model,
                    rects_a=placements[floor_id][left_id],
                    rects_b=placements[floor_id][right_id],
                    max_w=envelope_w_cells,
                    max_h=envelope_h_cells,
                    prefix=f"{_slug(floor_id)}_adj_{_slug(left_id)}_{_slug(right_id)}",
                    required=True,
                )

        if stair_spec is not None:
            for floor_id, hall_id in stair_spec.connects.items():
                if floor_id not in placements:
                    raise ValueError(f"stair connects references unknown floor '{floor_id}'")
                if stair_spec.id not in placements[floor_id]:
                    raise ValueError(f"stair '{stair_spec.id}' is missing on floor '{floor_id}'")
                if hall_id not in placements[floor_id]:
                    raise ValueError(f"stair connect hall '{hall_id}' is missing on floor '{floor_id}'")
                self._touching_constraint(
                    model=model,
                    rects_a=placements[floor_id][stair_spec.id],
                    rects_b=placements[floor_id][hall_id],
                    max_w=envelope_w_cells,
                    max_h=envelope_h_cells,
                    prefix=f"{_slug(floor_id)}_{_slug(stair_spec.id)}_{_slug(hall_id)}",
                    required=True,
                )

        for floor_id, floor in spec.floors.items():
            toilet_ids = [s.id for s in floor.spaces if s.type in {"toilet", "wc"}]
            ldk_ids = [s.id for s in floor.spaces if s.type == "ldk"]
            for toilet_id in toilet_ids:
                for ldk_id in ldk_ids:
                    self._enforce_non_adjacent(
                        model=model,
                        rects_a=placements[floor_id][toilet_id],
                        rects_b=placements[floor_id][ldk_id],
                        prefix=f"{_slug(floor_id)}_wc_ldk_{_slug(toilet_id)}_{_slug(ldk_id)}",
                    )

        for floor_id, floor in spec.floors.items():
            wet_ids = [s.id for s in floor.spaces if s.type in WET_SPACE_TYPES]
            if not wet_ids:
                continue

            adjacency_edges: dict[tuple[str, str], cp_model.IntVar] = {}
            for index, left_id in enumerate(wet_ids):
                for right_id in wet_ids[index + 1 :]:
                    edge = self._touching_constraint(
                        model=model,
                        rects_a=placements[floor_id][left_id],
                        rects_b=placements[floor_id][right_id],
                        max_w=envelope_w_cells,
                        max_h=envelope_h_cells,
                        prefix=f"{_slug(floor_id)}_wet_{_slug(left_id)}_{_slug(right_id)}",
                        required=False,
                    )
                    adjacency_edges[(left_id, right_id)] = edge

            if len(wet_ids) >= 2 and adjacency_edges:
                model.Add(sum(adjacency_edges.values()) >= len(wet_ids) - 1)
                for wet_id in wet_ids:
                    incident = [
                        edge
                        for (left_id, right_id), edge in adjacency_edges.items()
                        if left_id == wet_id or right_id == wet_id
                    ]
                    if incident:
                        model.AddBoolOr(incident)

            hall_ids = [s.id for s in floor.spaces if s.type == "hall"]
            if not hall_ids:
                raise ValueError(f"wet modules on floor {floor_id} require at least one hall")
            hall_touch_vars: list[cp_model.IntVar] = []
            for wet_id in wet_ids:
                for hall_id in hall_ids:
                    hall_touch_vars.append(
                        self._touching_constraint(
                            model=model,
                            rects_a=placements[floor_id][wet_id],
                            rects_b=placements[floor_id][hall_id],
                            max_w=envelope_w_cells,
                            max_h=envelope_h_cells,
                            prefix=f"{_slug(floor_id)}_wet_hall_{_slug(wet_id)}_{_slug(hall_id)}",
                            required=False,
                        )
                    )
            model.AddBoolOr(hall_touch_vars)

        objective_terms = [50 * v for v in major_room_alignment_penalties]
        objective_terms.extend(weight * var for var, weight in target_shortfalls)
        objective_terms.extend(weight * var for var, weight in target_overshoots)
        objective_terms.extend(5 * v for v in shape_balance_penalties)
        objective_terms.extend(8 * v for v in floor_compactness_terms)
        objective_terms.extend(10 * v for v in hall_area_penalties)
        if objective_terms:
            model.Minimize(sum(objective_terms))

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.max_time_seconds
        solver.parameters.num_search_workers = self.num_workers
        status = solver.Solve(model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            raise RuntimeError(f"unable to produce a valid plan (status={solver.StatusName(status)})")

        floor_solutions: dict[str, FloorSolution] = {}
        for floor_id, floor in spec.floors.items():
            solved_spaces: dict[str, SpaceGeometry] = {}
            for space in floor.spaces:
                rects = [
                    Rect(
                        x=cells_to_mm(solver.Value(rect.x), spec.grid.minor),
                        y=cells_to_mm(solver.Value(rect.y), spec.grid.minor),
                        w=cells_to_mm(solver.Value(rect.w), spec.grid.minor),
                        h=cells_to_mm(solver.Value(rect.h), spec.grid.minor),
                    )
                    for rect in placements[floor_id][space.id]
                ]
                solved_spaces[space.id] = SpaceGeometry(id=space.id, type=space.type, rects=rects)

            stair_geometry = None
            if stair_spec is not None and stair_spec.id in placements[floor_id] and stair_footprint is not None:
                stair_components = [
                    Rect(
                        x=cells_to_mm(solver.Value(rect.x), spec.grid.minor),
                        y=cells_to_mm(solver.Value(rect.y), spec.grid.minor),
                        w=cells_to_mm(solver.Value(rect.w), spec.grid.minor),
                        h=cells_to_mm(solver.Value(rect.h), spec.grid.minor),
                    )
                    for rect in placements[floor_id][stair_spec.id]
                ]
                min_x = min(component.x for component in stair_components)
                min_y = min(component.y for component in stair_components)
                max_x = max(component.x2 for component in stair_components)
                max_y = max(component.y2 for component in stair_components)
                stair_geometry = StairGeometry(
                    id=stair_spec.id,
                    type=stair_spec.type,
                    bbox=Rect(
                        x=min_x,
                        y=min_y,
                        w=max_x - min_x,
                        h=max_y - min_y,
                    ),
                    components=stair_components,
                    riser_count=stair_footprint.riser_count,
                    tread_count=stair_footprint.tread_count,
                    landing_size=stair_footprint.landing_mm,
                    connects=stair_spec.connects,
                )

            floor_solutions[floor_id] = FloorSolution(
                id=floor_id,
                spaces=solved_spaces,
                stair=stair_geometry,
                topology=list(floor.topology.adjacency),
            )

        return PlanSolution(
            units=spec.units,
            grid=spec.grid,
            envelope=spec.site.envelope,
            north=spec.site.north,
            floors=floor_solutions,
        )

    def _new_rect(
        self,
        model: cp_model.CpModel,
        prefix: str,
        max_w: int,
        max_h: int,
        fixed_w: int | None = None,
        fixed_h: int | None = None,
        shared_x: cp_model.IntVar | None = None,
        shared_y: cp_model.IntVar | None = None,
        shared_x_offset: int = 0,
        shared_y_offset: int = 0,
    ) -> RectVar:
        w = (
            model.NewIntVar(fixed_w, fixed_w, f"{prefix}_w")
            if fixed_w is not None
            else model.NewIntVar(1, max_w, f"{prefix}_w")
        )
        h = (
            model.NewIntVar(fixed_h, fixed_h, f"{prefix}_h")
            if fixed_h is not None
            else model.NewIntVar(1, max_h, f"{prefix}_h")
        )

        if shared_x is None:
            x = model.NewIntVar(0, max_w - 1, f"{prefix}_x")
        else:
            x = model.NewIntVar(0, max_w - 1, f"{prefix}_x")
            model.Add(x == shared_x + shared_x_offset)

        if shared_y is None:
            y = model.NewIntVar(0, max_h - 1, f"{prefix}_y")
        else:
            y = model.NewIntVar(0, max_h - 1, f"{prefix}_y")
            model.Add(y == shared_y + shared_y_offset)
        x_end = model.NewIntVar(1, max_w, f"{prefix}_x_end")
        y_end = model.NewIntVar(1, max_h, f"{prefix}_y_end")
        model.Add(x_end == x + w)
        model.Add(y_end == y + h)
        model.Add(x_end <= max_w)
        model.Add(y_end <= max_h)

        area = model.NewIntVar(1, max_w * max_h, f"{prefix}_area")
        model.AddMultiplicationEquality(area, [w, h])

        x_interval = model.NewIntervalVar(x, w, x_end, f"{prefix}_x_interval")
        y_interval = model.NewIntervalVar(y, h, y_end, f"{prefix}_y_interval")
        return RectVar(
            x=x,
            y=y,
            w=w,
            h=h,
            x_end=x_end,
            y_end=y_end,
            area=area,
            x_interval=x_interval,
            y_interval=y_interval,
        )

    def _touching_constraint(
        self,
        model: cp_model.CpModel,
        rects_a: list[RectVar],
        rects_b: list[RectVar],
        max_w: int,
        max_h: int,
        prefix: str,
        required: bool,
    ) -> cp_model.IntVar:
        if not rects_a or not rects_b:
            raise ValueError("touching constraints require non-empty rectangle sets")

        touch_candidates: list[cp_model.IntVar] = []
        for i, rect_a in enumerate(rects_a):
            for j, rect_b in enumerate(rects_b):
                touch_candidates.append(
                    self._pair_touch_bool(
                        model=model,
                        rect_a=rect_a,
                        rect_b=rect_b,
                        max_w=max_w,
                        max_h=max_h,
                        prefix=f"{prefix}_{i}_{j}",
                    )
                )

        touch_any = model.NewBoolVar(f"{prefix}_touch_any")
        model.AddMaxEquality(touch_any, touch_candidates)
        if required:
            model.Add(touch_any == 1)
        return touch_any

    def _pair_touch_bool(
        self,
        model: cp_model.CpModel,
        rect_a: RectVar,
        rect_b: RectVar,
        max_w: int,
        max_h: int,
        prefix: str,
    ) -> cp_model.IntVar:
        overlap_x = self._overlap_length(
            model=model,
            a_start=rect_a.x,
            a_end=rect_a.x_end,
            b_start=rect_b.x,
            b_end=rect_b.x_end,
            limit=max_w,
            prefix=f"{prefix}_ovx",
        )
        overlap_y = self._overlap_length(
            model=model,
            a_start=rect_a.y,
            a_end=rect_a.y_end,
            b_start=rect_b.y,
            b_end=rect_b.y_end,
            limit=max_h,
            prefix=f"{prefix}_ovy",
        )

        left = model.NewBoolVar(f"{prefix}_left")
        right = model.NewBoolVar(f"{prefix}_right")
        up = model.NewBoolVar(f"{prefix}_up")
        down = model.NewBoolVar(f"{prefix}_down")

        model.Add(rect_a.x_end == rect_b.x).OnlyEnforceIf(right)
        model.Add(overlap_y >= 1).OnlyEnforceIf(right)

        model.Add(rect_b.x_end == rect_a.x).OnlyEnforceIf(left)
        model.Add(overlap_y >= 1).OnlyEnforceIf(left)

        model.Add(rect_a.y_end == rect_b.y).OnlyEnforceIf(down)
        model.Add(overlap_x >= 1).OnlyEnforceIf(down)

        model.Add(rect_b.y_end == rect_a.y).OnlyEnforceIf(up)
        model.Add(overlap_x >= 1).OnlyEnforceIf(up)

        touch = model.NewBoolVar(f"{prefix}_touch")
        model.AddMaxEquality(touch, [left, right, up, down])
        return touch

    def _overlap_length(
        self,
        model: cp_model.CpModel,
        a_start: cp_model.IntVar,
        a_end: cp_model.IntVar,
        b_start: cp_model.IntVar,
        b_end: cp_model.IntVar,
        limit: int,
        prefix: str,
    ) -> cp_model.IntVar:
        low = model.NewIntVar(0, limit, f"{prefix}_low")
        high = model.NewIntVar(0, limit, f"{prefix}_high")
        overlap = model.NewIntVar(-limit, limit, f"{prefix}_ov")
        model.AddMaxEquality(low, [a_start, b_start])
        model.AddMinEquality(high, [a_end, b_end])
        model.Add(overlap == high - low)
        return overlap

    def _enforce_non_adjacent(
        self,
        model: cp_model.CpModel,
        rects_a: list[RectVar],
        rects_b: list[RectVar],
        prefix: str,
    ) -> None:
        for i, rect_a in enumerate(rects_a):
            for j, rect_b in enumerate(rects_b):
                a_right = model.NewBoolVar(f"{prefix}_{i}_{j}_a_right")
                b_right = model.NewBoolVar(f"{prefix}_{i}_{j}_b_right")
                a_below = model.NewBoolVar(f"{prefix}_{i}_{j}_a_below")
                b_below = model.NewBoolVar(f"{prefix}_{i}_{j}_b_below")

                model.Add(rect_a.x >= rect_b.x_end + 1).OnlyEnforceIf(a_right)
                model.Add(rect_b.x >= rect_a.x_end + 1).OnlyEnforceIf(b_right)
                model.Add(rect_a.y >= rect_b.y_end + 1).OnlyEnforceIf(a_below)
                model.Add(rect_b.y >= rect_a.y_end + 1).OnlyEnforceIf(b_below)

                model.AddBoolOr([a_right, b_right, a_below, b_below])


def _component_count(space: SpaceSpec) -> int:
    if (
        space.type == "ldk"
        and "L2" in space.shape.allow
        and "rect" not in space.shape.allow
        and space.shape.rect_components_max >= 2
    ):
        return 2
    return 1


def _min_area_cells(space: SpaceSpec, minor_grid: int) -> int:
    if space.area.min_tatami is not None:
        return tatami_to_cells(space.area.min_tatami, minor_grid)
    if space.area.target_tatami is not None:
        return tatami_to_cells(space.area.target_tatami, minor_grid)
    default = DEFAULT_MIN_TATAMI.get(space.type)
    if default is not None:
        return tatami_to_cells(default, minor_grid)
    return 4


def _target_area_cells(space: SpaceSpec, minor_grid: int) -> int | None:
    if space.area.target_tatami is None:
        return None
    return tatami_to_cells(space.area.target_tatami, minor_grid)


def _shortfall_weight(space_type: str) -> int:
    if space_type == "hall":
        return 48
    if space_type in {"bedroom", "master_bedroom"}:
        return 36
    if space_type == "ldk":
        return 34
    if space_type == "entry":
        return 30
    return 28


def _overshoot_weight(space_type: str) -> int:
    if space_type == "hall":
        return 18
    if space_type == "entry":
        return 16
    if space_type in {"bedroom", "master_bedroom"}:
        return 12
    if space_type == "ldk":
        return 10
    if space_type == "storage":
        return 6
    return 9


def _max_area_cells(space: SpaceSpec, minor_grid: int) -> int | None:
    if space.type == "hall":
        return tatami_to_cells(5.0, minor_grid)
    if space.type == "entry":
        return tatami_to_cells(4.0, minor_grid)
    if space.type in {"bedroom", "master_bedroom"}:
        if space.area.target_tatami is not None:
            return tatami_to_cells(space.area.target_tatami * 1.8, minor_grid)
        return tatami_to_cells(14.0, minor_grid)
    if space.type == "ldk":
        if space.area.target_tatami is not None:
            return tatami_to_cells(space.area.target_tatami * 2.0, minor_grid)
        return tatami_to_cells(24.0, minor_grid)
    return None


def _min_width_cells(space: SpaceSpec, minor_grid: int) -> int:
    if space.size_constraints.min_width is not None:
        return mm_to_cells(space.size_constraints.min_width, minor_grid)
    if space.type == "ldk":
        return 4
    if space.type in {"bedroom", "master_bedroom"}:
        return 3
    if space.type == "entry":
        return 2
    if space.type == "hall":
        return 2
    return 1


def _find_global_stair(spec: PlanSpec) -> StairSpec | None:
    stair: StairSpec | None = None
    for floor in spec.floors.values():
        if floor.core.stair is None:
            continue
        if stair is None:
            stair = floor.core.stair
            continue
        if floor.core.stair.id != stair.id:
            raise ValueError("MVP supports one shared stair id across floors")
    return stair


def _compute_stair_footprint(stair: StairSpec, minor_grid: int) -> StairFootprint:
    width_mm = ceil_to_grid(stair.width, minor_grid)
    width_cells = mm_to_cells(width_mm, minor_grid)
    riser_count = max(2, int(round(stair.floor_height / max(1, stair.riser_pref))))
    tread_count = max(1, riser_count - 1)
    tread_mm = max(1, stair.tread_pref)

    if stair.type == "straight":
        run_mm = ceil_to_grid(tread_count * tread_mm, minor_grid)
        run_cells = max(1, mm_to_cells(run_mm, minor_grid))
        components = [("flight1", 0, 0, width_cells, run_cells)]
        bbox_w_cells = width_cells
        bbox_h_cells = run_cells
    elif stair.type == "L_landing":
        run1_treads = max(1, int(math.ceil(tread_count / 2)))
        run2_treads = max(1, tread_count - run1_treads)
        run1_mm = ceil_to_grid(run1_treads * tread_mm, minor_grid)
        run2_mm = ceil_to_grid(run2_treads * tread_mm, minor_grid)
        run1_cells = max(1, mm_to_cells(run1_mm, minor_grid))
        run2_cells = max(1, mm_to_cells(run2_mm, minor_grid))
        components = [
            ("flight1", 0, 0, run1_cells, width_cells),
            ("landing", run1_cells, 0, width_cells, width_cells),
            ("flight2", run1_cells, width_cells, width_cells, run2_cells),
        ]
        bbox_w_cells = run1_cells + width_cells
        bbox_h_cells = width_cells + run2_cells
    else:
        raise ValueError(f"unsupported stair type '{stair.type}'")

    return StairFootprint(
        w_cells=bbox_w_cells,
        h_cells=bbox_h_cells,
        components=components,
        riser_count=riser_count,
        tread_count=tread_count,
        landing_mm=(width_mm, width_mm),
    )


def _slug(value: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in value)
