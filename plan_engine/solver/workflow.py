from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ortools.sat.python import cp_model

from plan_engine.constants import (
    MAJOR_ROOM_TYPES,
    WET_MODULE_SIZES_MM,
    WET_SPACE_TYPES,
    is_indoor_space_type,
    mm_to_cells,
)
from plan_engine.solver.constraints import (
    edge_touch_constraint,
    enforce_exterior_touch,
    enforce_internal_portal_edge,
    enforce_non_adjacent,
    touching_constraint,
)
from plan_engine.solver.rect_var import (
    RectVar,
    StairFootprint,
    _compute_stair_footprint,
    _find_global_stair,
    _slug,
    new_rect,
)
from plan_engine.solver.space_specs import (
    _component_count,
    _max_area_cells,
    _min_area_cells,
    _min_width_cells,
    _overshoot_weight,
    _shortfall_weight,
    _target_area_cells,
)
from plan_engine.stair_logic import ordered_floor_ids, stair_portal_for_floor

if TYPE_CHECKING:
    from plan_engine.models import PlanSpec, StairSpec

TOILET_SPACE_TYPES = frozenset({"toilet", "wc"})
WET_CORE_SPACE_TYPES = frozenset({"washroom", "bath"})
CIRCULATION_SPACE_TYPES = frozenset({"hall", "entry"})


@dataclass
class SolveContext:
    """Mutable container holding all state for a single solve run."""

    model: cp_model.CpModel
    envelope_w_cells: int
    envelope_h_cells: int
    max_area: int
    placements: dict[str, dict[str, list[RectVar]]]
    target_shortfalls: list[tuple[cp_model.IntVar, int]]
    target_overshoots: list[tuple[cp_model.IntVar, int]]
    major_room_alignment_penalties: list[cp_model.IntVar]
    shape_balance_penalties: list[cp_model.IntVar]
    hall_area_penalties: list[cp_model.IntVar]
    floor_compactness_terms: list[cp_model.IntVar]
    topology_soft_penalties: list[tuple[cp_model.IntVar, int]]
    floor_area_vars: dict[str, list[cp_model.IntVar]]
    floor_indoor_area_vars: dict[str, list[cp_model.IntVar]]
    floor_buildable_masks: dict[str, list[tuple[int, int, int, int]]]
    floor_buildable_area_cells: dict[str, int]
    ordered_floors: list[str]
    floor_rank: dict[str, int]
    stair_spec: StairSpec | None
    stair_footprint: StairFootprint | None
    stair_x: cp_model.IntVar | None
    stair_y: cp_model.IntVar | None
    floors_with_stair: set[str]
    skip_portal_edge: bool
    skip_internal_portal: bool
    debug_solver: bool
    forced_stair_x_cells: int | None
    forced_stair_y_cells: int | None


def build_context(spec: PlanSpec) -> SolveContext:
    """Initialize a SolveContext from a PlanSpec, including stair setup and environment parsing."""
    skip_portal_edge = os.getenv("PLAN_ENGINE_SKIP_PORTAL_EDGE") == "1"
    skip_internal_portal = os.getenv("PLAN_ENGINE_SKIP_INTERNAL_PORTAL") == "1"
    debug_solver = os.getenv("PLAN_ENGINE_DEBUG_SOLVER") == "1"
    forced_stair_x_cells_raw = os.getenv("PLAN_ENGINE_FORCE_STAIR_X_CELLS")
    forced_stair_y_cells_raw = os.getenv("PLAN_ENGINE_FORCE_STAIR_Y_CELLS")
    forced_stair_x_cells = int(forced_stair_x_cells_raw) if forced_stair_x_cells_raw is not None else None
    forced_stair_y_cells = int(forced_stair_y_cells_raw) if forced_stair_y_cells_raw is not None else None

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
    topology_soft_penalties: list[tuple[cp_model.IntVar, int]] = []
    floor_area_vars: dict[str, list[cp_model.IntVar]] = {fid: [] for fid in spec.floors}
    floor_indoor_area_vars: dict[str, list[cp_model.IntVar]] = {fid: [] for fid in spec.floors}
    floor_buildable_masks: dict[str, list[tuple[int, int, int, int]]] = {}
    floor_buildable_area_cells: dict[str, int] = {}

    for floor_id, floor in spec.floors.items():
        mask_cells: list[tuple[int, int, int, int]] = []
        if floor.buildable_mask:
            for rect in floor.buildable_mask:
                mask_cells.append(
                    (
                        mm_to_cells(rect.x, spec.grid.minor),
                        mm_to_cells(rect.y, spec.grid.minor),
                        mm_to_cells(rect.w, spec.grid.minor),
                        mm_to_cells(rect.h, spec.grid.minor),
                    )
                )
        if not mask_cells:
            mask_cells = [(0, 0, envelope_w_cells, envelope_h_cells)]
        floor_buildable_masks[floor_id] = mask_cells
        floor_buildable_area_cells[floor_id] = sum(w * h for _, _, w, h in mask_cells)

    ordered_floors = ordered_floor_ids(spec.floors.keys())
    floor_rank = {floor_id: idx for idx, floor_id in enumerate(ordered_floors)}
    stair_spec = _find_global_stair(spec)
    stair_footprint: StairFootprint | None = None
    stair_x: cp_model.IntVar | None = None
    stair_y: cp_model.IntVar | None = None
    floors_with_stair: set[str] = set()

    if stair_spec is not None:
        stair_footprint, stair_x, stair_y = _create_stair_anchor(
            model=model,
            spec=spec,
            stair_spec=stair_spec,
            envelope_w_cells=envelope_w_cells,
            envelope_h_cells=envelope_h_cells,
            forced_stair_x_cells=forced_stair_x_cells,
            forced_stair_y_cells=forced_stair_y_cells,
        )
        floors_with_stair = set(stair_spec.connects.keys())
        floors_with_stair.update(floor_id for floor_id, floor in spec.floors.items() if floor.core.stair is not None)
        floors_with_stair.intersection_update(spec.floors.keys())

    return SolveContext(
        model=model,
        envelope_w_cells=envelope_w_cells,
        envelope_h_cells=envelope_h_cells,
        max_area=max_area,
        placements=placements,
        target_shortfalls=target_shortfalls,
        target_overshoots=target_overshoots,
        major_room_alignment_penalties=major_room_alignment_penalties,
        shape_balance_penalties=shape_balance_penalties,
        hall_area_penalties=hall_area_penalties,
        floor_compactness_terms=floor_compactness_terms,
        topology_soft_penalties=topology_soft_penalties,
        floor_area_vars=floor_area_vars,
        floor_indoor_area_vars=floor_indoor_area_vars,
        floor_buildable_masks=floor_buildable_masks,
        floor_buildable_area_cells=floor_buildable_area_cells,
        ordered_floors=ordered_floors,
        floor_rank=floor_rank,
        stair_spec=stair_spec,
        stair_footprint=stair_footprint,
        stair_x=stair_x,
        stair_y=stair_y,
        floors_with_stair=floors_with_stair,
        skip_portal_edge=skip_portal_edge,
        skip_internal_portal=skip_internal_portal,
        debug_solver=debug_solver,
        forced_stair_x_cells=forced_stair_x_cells,
        forced_stair_y_cells=forced_stair_y_cells,
    )


def _create_stair_anchor(
    model: cp_model.CpModel,
    spec: PlanSpec,
    stair_spec: StairSpec,
    envelope_w_cells: int,
    envelope_h_cells: int,
    forced_stair_x_cells: int | None,
    forced_stair_y_cells: int | None,
) -> tuple[StairFootprint, cp_model.IntVar, cp_model.IntVar]:
    """Create shared stair position variables and compute stair footprint."""
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

    stair_x_cells = forced_stair_x_cells
    stair_y_cells = forced_stair_y_cells
    if stair_x_cells is None and stair_spec.placement_x is not None:
        stair_x_cells = mm_to_cells(stair_spec.placement_x, spec.grid.minor)
    if stair_y_cells is None and stair_spec.placement_y is not None:
        stair_y_cells = mm_to_cells(stair_spec.placement_y, spec.grid.minor)

    if stair_x_cells is not None:
        if stair_x_cells < 0 or stair_x_cells > envelope_w_cells - stair_footprint.w_cells:
            raise ValueError("PLAN_ENGINE_FORCE_STAIR_X_CELLS is out of range")
        model.Add(stair_x == stair_x_cells)
    if stair_y_cells is not None:
        if stair_y_cells < 0 or stair_y_cells > envelope_h_cells - stair_footprint.h_cells:
            raise ValueError("PLAN_ENGINE_FORCE_STAIR_Y_CELLS is out of range")
        model.Add(stair_y == stair_y_cells)

    return stair_footprint, stair_x, stair_y


def _constrain_rect_within_buildable_union(
    model: cp_model.CpModel,
    rect: RectVar,
    allowed_regions: list[tuple[int, int, int, int]],
    prefix: str,
) -> None:
    """Constrain one rectangle to lie fully inside a union of allowed regions.

    Args:
        model: CP-SAT model receiving constraints.
        rect: Rectangle variable to constrain.
        allowed_regions: Regions as ``(x, y, w, h)`` in cell units.
        prefix: Variable-name prefix for helper booleans.

    Returns:
        None. Constraints are added in-place.
    """
    if len(allowed_regions) == 1:
        x, y, w, h = allowed_regions[0]
        model.Add(rect.x >= x)
        model.Add(rect.y >= y)
        model.Add(rect.x_end <= x + w)
        model.Add(rect.y_end <= y + h)
        return

    indicators: list[cp_model.IntVar] = []
    for index, (x, y, w, h) in enumerate(allowed_regions):
        inside = model.NewBoolVar(f"{prefix}_in_buildable_{index}")
        indicators.append(inside)
        model.Add(rect.x >= x).OnlyEnforceIf(inside)
        model.Add(rect.y >= y).OnlyEnforceIf(inside)
        model.Add(rect.x_end <= x + w).OnlyEnforceIf(inside)
        model.Add(rect.y_end <= y + h).OnlyEnforceIf(inside)
    model.AddBoolOr(indicators)


def create_space_variables(spec: PlanSpec, ctx: SolveContext) -> None:
    """Create CP-SAT rectangle variables and space-local constraints.

    Args:
        spec: Parsed plan specification.
        ctx: Mutable solve context carrying model state and accumulators.

    Returns:
        None. Variables/constraints are added to ``ctx.model`` in place.
    """
    max_strip_width_cells = max(1, int(ctx.envelope_w_cells * 0.7))
    max_strip_depth_cells = max(1, int(ctx.envelope_h_cells * 0.7))
    for floor_id, floor in spec.floors.items():
        buildable_regions = ctx.floor_buildable_masks[floor_id]
        for space in floor.spaces:
            indoor_space = is_indoor_space_type(space.type)
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
                rect = new_rect(
                    model=ctx.model,
                    prefix=prefix,
                    max_w=ctx.envelope_w_cells,
                    max_h=ctx.envelope_h_cells,
                    fixed_w=fixed_w_cells,
                    fixed_h=fixed_h_cells,
                )
                rects.append(rect)

            ctx.placements[floor_id][space.id] = rects
            min_width_cells = _min_width_cells(space, spec.grid.minor)
            for idx, rect in enumerate(rects):
                min_dim = ctx.model.NewIntVar(
                    1,
                    max(ctx.envelope_w_cells, ctx.envelope_h_cells),
                    f"{_slug(floor_id)}_{_slug(space.id)}_{idx}_min_dim",
                )
                ctx.model.AddMinEquality(min_dim, [rect.w, rect.h])
                ctx.model.Add(min_dim >= min_width_cells)
                if space.type in {"bedroom", "master_bedroom"} and space.size_constraints.min_width is None:
                    # Fallback default only when spec does not provide an explicit min width.
                    ctx.model.Add(min_dim >= mm_to_cells(2275, spec.grid.minor))
                if space.type == "hall":
                    max_hall_width_cells = mm_to_cells(1820, spec.grid.minor)
                    ctx.model.Add(min_dim <= max_hall_width_cells)
                if fixed_dims is None and space.type in {"ldk", "master_bedroom"}:
                    # Prevent unrealistic full-depth/full-width strips on anchor rooms.
                    ctx.model.Add(rect.w <= max_strip_width_cells)
                    ctx.model.Add(rect.h <= max_strip_depth_cells)
                if indoor_space:
                    _constrain_rect_within_buildable_union(
                        model=ctx.model,
                        rect=rect,
                        allowed_regions=buildable_regions,
                        prefix=f"{_slug(floor_id)}_{_slug(space.id)}_{idx}",
                    )

            area_sum = ctx.model.NewIntVar(
                1,
                ctx.max_area * component_count,
                f"{_slug(floor_id)}_{_slug(space.id)}_area_sum",
            )
            ctx.model.Add(area_sum == sum(r.area for r in rects))
            ctx.model.Add(area_sum >= _min_area_cells(space, spec.grid.minor))
            if space.type == "hall":
                ctx.hall_area_penalties.append(area_sum)

            target_area_cells = _target_area_cells(space, spec.grid.minor)
            if target_area_cells is not None:
                shortfall = ctx.model.NewIntVar(
                    0,
                    ctx.max_area * component_count,
                    f"{_slug(floor_id)}_{_slug(space.id)}_area_shortfall",
                )
                ctx.model.Add(shortfall >= target_area_cells - area_sum)
                ctx.target_shortfalls.append((shortfall, _shortfall_weight(space.type)))

                overshoot = ctx.model.NewIntVar(
                    0,
                    ctx.max_area * component_count,
                    f"{_slug(floor_id)}_{_slug(space.id)}_area_overshoot",
                )
                ctx.model.Add(overshoot >= area_sum - target_area_cells)
                ctx.target_overshoots.append((overshoot, _overshoot_weight(space.type)))

            max_area_cells = _max_area_cells(space, spec.grid.minor)
            if max_area_cells is not None:
                ctx.model.Add(area_sum <= max_area_cells)

            ctx.floor_area_vars[floor_id].append(area_sum)
            if indoor_space:
                ctx.floor_indoor_area_vars[floor_id].append(area_sum)

            if component_count > 1:
                for idx in range(1, component_count):
                    touching_constraint(
                        model=ctx.model,
                        rects_a=[rects[idx - 1]],
                        rects_b=[rects[idx]],
                        max_w=ctx.envelope_w_cells,
                        max_h=ctx.envelope_h_cells,
                        prefix=f"{_slug(floor_id)}_{_slug(space.id)}_chain_{idx - 1}_{idx}",
                        required=True,
                    )

            if space.type == "entry":
                enforce_exterior_touch(
                    model=ctx.model,
                    rects=rects,
                    max_w=ctx.envelope_w_cells,
                    max_h=ctx.envelope_h_cells,
                    prefix=f"{_slug(floor_id)}_{_slug(space.id)}_ext",
                )
            elif space.type in MAJOR_ROOM_TYPES:
                enforce_exterior_touch(
                    model=ctx.model,
                    rects=rects,
                    max_w=ctx.envelope_w_cells,
                    max_h=ctx.envelope_h_cells,
                    prefix=f"{_slug(floor_id)}_{_slug(space.id)}_major_ext",
                )

            if space.type in MAJOR_ROOM_TYPES:
                for idx, rect in enumerate(rects):
                    odd_w = ctx.model.NewIntVar(0, 1, f"{_slug(floor_id)}_{_slug(space.id)}_{idx}_odd_w")
                    odd_h = ctx.model.NewIntVar(0, 1, f"{_slug(floor_id)}_{_slug(space.id)}_{idx}_odd_h")
                    ctx.model.AddModuloEquality(odd_w, rect.w, 2)
                    ctx.model.AddModuloEquality(odd_h, rect.h, 2)
                    ctx.major_room_alignment_penalties.extend([odd_w, odd_h])

            if space.type not in {"hall", "toilet", "wc", "washroom", "bath"}:
                for idx, rect in enumerate(rects):
                    if space.type in {"bedroom", "master_bedroom"}:
                        ctx.model.Add(2 * rect.w <= 5 * rect.h)
                        ctx.model.Add(2 * rect.h <= 5 * rect.w)
                    else:
                        ctx.model.Add(rect.w <= 4 * rect.h)
                        ctx.model.Add(rect.h <= 4 * rect.w)
                    aspect_delta = ctx.model.NewIntVar(
                        0,
                        max(ctx.envelope_w_cells, ctx.envelope_h_cells),
                        f"{_slug(floor_id)}_{_slug(space.id)}_{idx}_aspect_delta",
                    )
                    ctx.model.Add(aspect_delta >= rect.w - rect.h)
                    ctx.model.Add(aspect_delta >= rect.h - rect.w)
                    ctx.shape_balance_penalties.append(aspect_delta)

        if (
            ctx.stair_spec is not None
            and floor_id in ctx.floors_with_stair
            and ctx.stair_footprint is not None
            and ctx.stair_x is not None
            and ctx.stair_y is not None
        ):
            stair_rects: list[RectVar] = []
            for component_name, dx, dy, comp_w, comp_h in ctx.stair_footprint.components:
                stair_rect = new_rect(
                    model=ctx.model,
                    prefix=f"{_slug(floor_id)}_{_slug(ctx.stair_spec.id)}_{_slug(component_name)}",
                    max_w=ctx.envelope_w_cells,
                    max_h=ctx.envelope_h_cells,
                    fixed_w=comp_w,
                    fixed_h=comp_h,
                    shared_x=ctx.stair_x,
                    shared_y=ctx.stair_y,
                    shared_x_offset=dx,
                    shared_y_offset=dy,
                )
                _constrain_rect_within_buildable_union(
                    model=ctx.model,
                    rect=stair_rect,
                    allowed_regions=buildable_regions,
                    prefix=f"{_slug(floor_id)}_{_slug(ctx.stair_spec.id)}_{_slug(component_name)}",
                )
                stair_rects.append(stair_rect)
                ctx.floor_area_vars[floor_id].append(stair_rect.area)
                ctx.floor_indoor_area_vars[floor_id].append(stair_rect.area)
            ctx.placements[floor_id][ctx.stair_spec.id] = stair_rects


def add_floor_packing_constraints(ctx: SolveContext) -> None:
    """Add non-overlap, compactness, and full-coverage constraints per floor."""
    for floor_id, entities in ctx.placements.items():
        all_rects = [rect for rects in entities.values() for rect in rects]
        if not all_rects:
            continue

        ctx.model.AddNoOverlap2D(
            [r.x_interval for r in all_rects],
            [r.y_interval for r in all_rects],
        )

        min_x = ctx.model.NewIntVar(0, ctx.envelope_w_cells, f"{_slug(floor_id)}_min_x")
        min_y = ctx.model.NewIntVar(0, ctx.envelope_h_cells, f"{_slug(floor_id)}_min_y")
        max_x = ctx.model.NewIntVar(0, ctx.envelope_w_cells, f"{_slug(floor_id)}_max_x")
        max_y = ctx.model.NewIntVar(0, ctx.envelope_h_cells, f"{_slug(floor_id)}_max_y")
        ctx.model.AddMinEquality(min_x, [rect.x for rect in all_rects])
        ctx.model.AddMinEquality(min_y, [rect.y for rect in all_rects])
        ctx.model.AddMaxEquality(max_x, [rect.x_end for rect in all_rects])
        ctx.model.AddMaxEquality(max_y, [rect.y_end for rect in all_rects])

        span_x = ctx.model.NewIntVar(1, ctx.envelope_w_cells, f"{_slug(floor_id)}_span_x")
        span_y = ctx.model.NewIntVar(1, ctx.envelope_h_cells, f"{_slug(floor_id)}_span_y")
        ctx.model.Add(span_x == max_x - min_x)
        ctx.model.Add(span_y == max_y - min_y)
        ctx.floor_compactness_terms.extend([span_x, span_y])

        indoor_target = ctx.floor_buildable_area_cells.get(floor_id, ctx.max_area)
        used_area = ctx.model.NewIntVar(0, ctx.max_area, f"{_slug(floor_id)}_used_indoor_area")
        ctx.model.Add(used_area == sum(ctx.floor_indoor_area_vars[floor_id]))
        ctx.model.Add(used_area == indoor_target)


def add_topology_constraints(spec: PlanSpec, ctx: SolveContext) -> None:
    """Enforce topology adjacency with required/soft strengths.

    Required edges are hard constraints. Preferred/optional edges are modelled
    as soft penalties that encourage touching without forcing infeasibility.
    """
    for floor_id, floor in spec.floors.items():
        space_type_by_id = {space.id: space.type for space in floor.spaces}
        if ctx.stair_spec is not None and floor_id in ctx.floors_with_stair:
            space_type_by_id[ctx.stair_spec.id] = "stair"
        incident_touches: dict[str, list[cp_model.IntVar]] = {entity_id: [] for entity_id in ctx.placements[floor_id]}
        declared_neighbors: dict[str, set[str]] = {entity_id: set() for entity_id in ctx.placements[floor_id]}
        touch_by_pair: dict[tuple[str, str], cp_model.IntVar] = {}

        for edge in floor.topology.adjacency:
            left_id = edge.left_id
            right_id = edge.right_id
            if left_id not in ctx.placements[floor_id]:
                raise ValueError(f"unknown topology id '{left_id}' in floor {floor_id}")
            if right_id not in ctx.placements[floor_id]:
                raise ValueError(f"unknown topology id '{right_id}' in floor {floor_id}")
            strength = _resolve_adjacency_strength(
                declared_strength=edge.strength,
                left_type=space_type_by_id.get(left_id, "unknown"),
                right_type=space_type_by_id.get(right_id, "unknown"),
            )
            touch_any = touching_constraint(
                model=ctx.model,
                rects_a=ctx.placements[floor_id][left_id],
                rects_b=ctx.placements[floor_id][right_id],
                max_w=ctx.envelope_w_cells,
                max_h=ctx.envelope_h_cells,
                prefix=f"{_slug(floor_id)}_adj_{_slug(left_id)}_{_slug(right_id)}",
                required=False,
            )
            declared_neighbors[left_id].add(right_id)
            declared_neighbors[right_id].add(left_id)
            touch_by_pair[(left_id, right_id)] = touch_any
            touch_by_pair[(right_id, left_id)] = touch_any
            incident_touches[left_id].append(touch_any)
            incident_touches[right_id].append(touch_any)
            if strength == "required":
                ctx.model.Add(touch_any == 1)
            else:
                missing_touch = ctx.model.NewBoolVar(
                    f"{_slug(floor_id)}_adj_{_slug(left_id)}_{_slug(right_id)}_missing"
                )
                ctx.model.Add(missing_touch + touch_any == 1)
                penalty_weight = 26 if strength == "preferred" else 12
                ctx.topology_soft_penalties.append((missing_touch, penalty_weight))

        for entity_id, entity_type in space_type_by_id.items():
            if entity_type in WET_SPACE_TYPES or entity_type == "hall":
                continue
            neighbors = incident_touches.get(entity_id, [])
            if not neighbors:
                continue
            # Every primary space must realize at least one declared adjacency edge.
            ctx.model.AddBoolOr(neighbors)

        for entity_id, entity_type in space_type_by_id.items():
            if is_indoor_space_type(entity_type):
                continue
            neighbor_ids = declared_neighbors.get(entity_id, set())
            indoor_neighbors = [
                neighbor_id
                for neighbor_id in neighbor_ids
                if neighbor_id in space_type_by_id and is_indoor_space_type(space_type_by_id[neighbor_id])
            ]
            if not indoor_neighbors:
                raise ValueError(
                    f"floor {floor_id} outdoor space '{entity_id}' requires topology adjacency to at least one indoor space"
                )
            realized: list[cp_model.IntVar] = []
            for indoor_neighbor in sorted(indoor_neighbors):
                touch = touch_by_pair.get((entity_id, indoor_neighbor))
                if touch is not None:
                    realized.append(touch)
            if realized:
                ctx.model.AddBoolOr(realized)


def add_bath_wash_adjacency_constraints(spec: PlanSpec, ctx: SolveContext) -> None:
    """Require each bath module to touch at least one washroom on the same floor.

    Args:
        spec: Parsed plan specification that defines floor spaces.
        ctx: Mutable solve context that owns CP-SAT variables and model.

    Returns:
        None. Constraints are added directly to ``ctx.model``.

    Raises:
        ValueError: If a floor defines bath spaces but no washroom spaces.
    """
    for floor_id, floor in spec.floors.items():
        bath_ids = [space.id for space in floor.spaces if space.type == "bath"]
        if not bath_ids:
            continue
        wash_ids = [space.id for space in floor.spaces if space.type == "washroom"]
        if not wash_ids:
            raise ValueError(f"floor {floor_id} has bath but no washroom")

        for bath_id in bath_ids:
            touch_vars: list[cp_model.IntVar] = []
            for wash_id in wash_ids:
                touch_vars.append(
                    touching_constraint(
                        model=ctx.model,
                        rects_a=ctx.placements[floor_id][bath_id],
                        rects_b=ctx.placements[floor_id][wash_id],
                        max_w=ctx.envelope_w_cells,
                        max_h=ctx.envelope_h_cells,
                        prefix=f"{_slug(floor_id)}_bath_wash_{_slug(bath_id)}_{_slug(wash_id)}",
                        required=False,
                    )
                )
            ctx.model.AddBoolOr(touch_vars)


def add_stair_connection_constraints(ctx: SolveContext) -> None:
    """Enforce stair-to-hall portal edge connectivity."""
    if ctx.stair_spec is None:
        return
    for floor_id, hall_id in ctx.stair_spec.connects.items():
        if floor_id not in ctx.placements:
            raise ValueError(f"stair connects references unknown floor '{floor_id}'")
        if ctx.stair_spec.id not in ctx.placements[floor_id]:
            raise ValueError(f"stair '{ctx.stair_spec.id}' is missing on floor '{floor_id}'")
        if hall_id not in ctx.placements[floor_id]:
            raise ValueError(f"stair connect hall '{hall_id}' is missing on floor '{floor_id}'")
        stair_rects = ctx.placements[floor_id][ctx.stair_spec.id]
        portal = stair_portal_for_floor(
            stair_type=ctx.stair_spec.type,
            floor_index=ctx.floor_rank[floor_id],
            floor_count=len(ctx.ordered_floors),
            component_count=len(stair_rects),
        )
        portal_rect = stair_rects[portal.component_index]
        if not ctx.skip_portal_edge:
            edge_touch_constraint(
                model=ctx.model,
                portal_rect=portal_rect,
                rects_b=ctx.placements[floor_id][hall_id],
                edge=portal.edge,
                max_w=ctx.envelope_w_cells,
                max_h=ctx.envelope_h_cells,
                prefix=f"{_slug(floor_id)}_{_slug(ctx.stair_spec.id)}_{_slug(hall_id)}_portal",
                required=True,
            )
        if not ctx.skip_internal_portal:
            enforce_internal_portal_edge(
                model=ctx.model,
                portal_rect=portal_rect,
                edge=portal.edge,
                max_w=ctx.envelope_w_cells,
                max_h=ctx.envelope_h_cells,
            )


def add_wc_ldk_non_adjacent_constraints(spec: PlanSpec, ctx: SolveContext) -> None:
    """Enforce separation between toilet/WC and LDK spaces."""
    for floor_id, floor in spec.floors.items():
        toilet_ids = [s.id for s in floor.spaces if s.type in {"toilet", "wc"}]
        ldk_ids = [s.id for s in floor.spaces if s.type == "ldk"]
        for toilet_id in toilet_ids:
            for ldk_id in ldk_ids:
                enforce_non_adjacent(
                    model=ctx.model,
                    rects_a=ctx.placements[floor_id][toilet_id],
                    rects_b=ctx.placements[floor_id][ldk_id],
                    prefix=f"{_slug(floor_id)}_wc_ldk_{_slug(toilet_id)}_{_slug(ldk_id)}",
                )


def add_wet_cluster_constraints(spec: PlanSpec, ctx: SolveContext) -> None:
    """Enforce wet-core clustering and hall adjacency.

    Wet-core clustering is defined over washroom/bath spaces only. Toilet/WC
    circulation is handled separately by ``add_toilet_circulation_constraints``.
    """
    for floor_id, floor in spec.floors.items():
        wet_ids = [s.id for s in floor.spaces if s.type in WET_SPACE_TYPES]
        if not wet_ids:
            continue

        wet_core_ids = [s.id for s in floor.spaces if s.type in WET_CORE_SPACE_TYPES]
        adjacency_edges: dict[tuple[str, str], cp_model.IntVar] = {}
        for index, left_id in enumerate(wet_core_ids):
            for right_id in wet_core_ids[index + 1 :]:
                edge = touching_constraint(
                    model=ctx.model,
                    rects_a=ctx.placements[floor_id][left_id],
                    rects_b=ctx.placements[floor_id][right_id],
                    max_w=ctx.envelope_w_cells,
                    max_h=ctx.envelope_h_cells,
                    prefix=f"{_slug(floor_id)}_wet_{_slug(left_id)}_{_slug(right_id)}",
                    required=False,
                )
                adjacency_edges[(left_id, right_id)] = edge

        if len(wet_core_ids) >= 2 and adjacency_edges:
            ctx.model.Add(sum(adjacency_edges.values()) >= len(wet_core_ids) - 1)
            for wet_id in wet_core_ids:
                incident = [
                    edge for (left_id, right_id), edge in adjacency_edges.items() if wet_id in (left_id, right_id)
                ]
                if incident:
                    ctx.model.AddBoolOr(incident)

        hall_ids = [s.id for s in floor.spaces if s.type == "hall"]
        if not hall_ids:
            raise ValueError(f"wet modules on floor {floor_id} require at least one hall")
        hall_touch_vars: list[cp_model.IntVar] = []
        for wet_id in wet_ids:
            for hall_id in hall_ids:
                hall_touch_vars.append(
                    touching_constraint(
                        model=ctx.model,
                        rects_a=ctx.placements[floor_id][wet_id],
                        rects_b=ctx.placements[floor_id][hall_id],
                        max_w=ctx.envelope_w_cells,
                        max_h=ctx.envelope_h_cells,
                        prefix=f"{_slug(floor_id)}_wet_hall_{_slug(wet_id)}_{_slug(hall_id)}",
                        required=False,
                    )
                )
        ctx.model.AddBoolOr(hall_touch_vars)


def add_toilet_circulation_constraints(spec: PlanSpec, ctx: SolveContext) -> None:
    """Require each toilet/WC to realize circulation topology adjacency.

    Each floor toilet must declare at least one topology edge to a circulation
    entity (hall/entry/stair). At solve time, at least one declared toilet
    circulation edge is enforced as physically realized touching.

    Args:
        spec: Parsed plan specification containing floor topology and spaces.
        ctx: Mutable solve context carrying CP-SAT variables and placements.

    Returns:
        None. Constraints are added to ``ctx.model``.

    Raises:
        ValueError: If a toilet has no declared circulation topology edge.
    """
    for floor_id, floor in spec.floors.items():
        space_type_by_id = {space.id: space.type for space in floor.spaces}
        toilet_ids = [space_id for space_id, space_type in space_type_by_id.items() if space_type in TOILET_SPACE_TYPES]
        if not toilet_ids:
            continue

        circulation_ids = {
            space_id for space_id, space_type in space_type_by_id.items() if space_type in CIRCULATION_SPACE_TYPES
        }
        if (
            ctx.stair_spec is not None
            and floor_id in ctx.floors_with_stair
            and ctx.stair_spec.id in ctx.placements[floor_id]
        ):
            circulation_ids.add(ctx.stair_spec.id)
        if not circulation_ids:
            raise ValueError(f"floor {floor_id} has toilet/wc but no hall/entry/stair circulation entity")

        topology_neighbors: dict[str, set[str]] = {toilet_id: set() for toilet_id in toilet_ids}
        for edge in floor.topology.adjacency:
            left_id = edge.left_id
            right_id = edge.right_id
            if left_id in topology_neighbors and right_id in circulation_ids:
                topology_neighbors[left_id].add(right_id)
            if right_id in topology_neighbors and left_id in circulation_ids:
                topology_neighbors[right_id].add(left_id)

        for toilet_id in toilet_ids:
            circulation_neighbors = sorted(topology_neighbors[toilet_id])
            if not circulation_neighbors:
                raise ValueError(
                    f"floor {floor_id} toilet '{toilet_id}' requires topology adjacency to hall/entry/stair"
                )

            touch_vars: list[cp_model.IntVar] = []
            for neighbor_id in circulation_neighbors:
                touch_vars.append(
                    touching_constraint(
                        model=ctx.model,
                        rects_a=ctx.placements[floor_id][toilet_id],
                        rects_b=ctx.placements[floor_id][neighbor_id],
                        max_w=ctx.envelope_w_cells,
                        max_h=ctx.envelope_h_cells,
                        prefix=f"{_slug(floor_id)}_toilet_circ_{_slug(toilet_id)}_{_slug(neighbor_id)}",
                        required=False,
                    )
                )
            ctx.model.AddBoolOr(touch_vars)


def add_wet_core_circulation_constraints(spec: PlanSpec, ctx: SolveContext) -> None:
    """Require wet core to realize at least one circulation topology adjacency.

    Wet core means washroom+bath spaces. This function ensures there is at
    least one declared topology edge from wet core to hall/entry/stair and
    that at least one such edge is physically realized.

    Args:
        spec: Parsed plan specification containing floor topology and spaces.
        ctx: Mutable solve context carrying CP-SAT variables and placements.

    Returns:
        None. Constraints are added to ``ctx.model``.

    Raises:
        ValueError: If wet core exists but no circulation topology edge is
            declared on a floor.
    """
    for floor_id, floor in spec.floors.items():
        space_type_by_id = {space.id: space.type for space in floor.spaces}
        wet_core_ids = [
            space_id
            for space_id, space_type in space_type_by_id.items()
            if space_type in WET_CORE_SPACE_TYPES
        ]
        if not wet_core_ids:
            continue

        circulation_ids = {
            space_id for space_id, space_type in space_type_by_id.items() if space_type in CIRCULATION_SPACE_TYPES
        }
        if (
            ctx.stair_spec is not None
            and floor_id in ctx.floors_with_stair
            and ctx.stair_spec.id in ctx.placements[floor_id]
        ):
            circulation_ids.add(ctx.stair_spec.id)
        if not circulation_ids:
            raise ValueError(f"floor {floor_id} has wet core but no hall/entry/stair circulation entity")

        declared_pairs: list[tuple[str, str]] = []
        for edge in floor.topology.adjacency:
            left_id = edge.left_id
            right_id = edge.right_id
            if left_id in wet_core_ids and right_id in circulation_ids:
                declared_pairs.append((left_id, right_id))
            if right_id in wet_core_ids and left_id in circulation_ids:
                declared_pairs.append((right_id, left_id))

        if not declared_pairs:
            raise ValueError(
                f"floor {floor_id} wet core requires topology adjacency to hall/entry/stair"
            )

        touch_vars: list[cp_model.IntVar] = []
        for wet_id, circulation_id in sorted(set(declared_pairs)):
            touch_vars.append(
                touching_constraint(
                    model=ctx.model,
                    rects_a=ctx.placements[floor_id][wet_id],
                    rects_b=ctx.placements[floor_id][circulation_id],
                    max_w=ctx.envelope_w_cells,
                    max_h=ctx.envelope_h_cells,
                    prefix=f"{_slug(floor_id)}_wet_core_circ_{_slug(wet_id)}_{_slug(circulation_id)}",
                    required=False,
                )
            )
        ctx.model.AddBoolOr(touch_vars)


def build_objective(ctx: SolveContext) -> None:
    """Assemble and minimize the weighted objective function."""
    objective_terms = [50 * v for v in ctx.major_room_alignment_penalties]
    objective_terms.extend(weight * var for var, weight in ctx.target_shortfalls)
    objective_terms.extend(weight * var for var, weight in ctx.target_overshoots)
    objective_terms.extend(12 * v for v in ctx.shape_balance_penalties)
    objective_terms.extend(8 * v for v in ctx.floor_compactness_terms)
    objective_terms.extend(10 * v for v in ctx.hall_area_penalties)
    objective_terms.extend(weight * var for var, weight in ctx.topology_soft_penalties)
    if objective_terms:
        ctx.model.Minimize(sum(objective_terms))


def _resolve_adjacency_strength(declared_strength: str, left_type: str, right_type: str) -> str:
    """Resolve adjacency strength from declared value and domain defaults.

    Args:
        declared_strength: Raw strength from DSL. ``auto`` means infer from
            space-type pair rules.
        left_type: Semantic type of the left entity.
        right_type: Semantic type of the right entity.

    Returns:
        One of ``required``, ``preferred``, or ``optional``.
    """
    strength = declared_strength.strip().lower()
    if strength in {"required", "preferred", "optional"}:
        return strength

    pair = tuple(sorted((left_type, right_type)))
    if pair in {
        ("bedroom", "hall"),
        ("hall", "master_bedroom"),
        ("hall", "storage"),
        ("master_bedroom", "storage"),
    }:
        return "preferred"
    return "required"
