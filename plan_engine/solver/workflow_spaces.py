from __future__ import annotations

from typing import TYPE_CHECKING

from plan_engine.constants import (
    MAJOR_ROOM_TYPES,
    WET_MODULE_SIZES_MM,
    is_indoor_space_type,
    mm_to_cells,
)
from plan_engine.solver.constraints import (
    enforce_exterior_touch,
    touching_constraint,
)
from plan_engine.solver.rect_var import (
    RectVar,
    _slug,
    new_rect,
)
from plan_engine.solver.space_specs import (
    _component_count,
    _embedded_closet_max_area_cells,
    _embedded_closet_min_area_cells,
    _embedded_closet_target_area_cells,
    _max_area_cells,
    _min_area_cells,
    _min_width_cells,
    _overshoot_weight,
    _shortfall_weight,
    _target_area_cells,
)
from plan_engine.solver.workflow_context import (
    SolveContext,
    _constrain_rect_within_buildable_union,
)

if TYPE_CHECKING:
    from plan_engine.models import FloorSpec, PlanSpec


def _embedded_closet_area_adjustments(
    floor: FloorSpec,
    minor_grid: int,
) -> dict[str, tuple[int, int, int]]:
    """Aggregate embedded closet area requirements per parent room.

    Args:
        floor: Floor specification containing embedded closet metadata.
        minor_grid: Minor grid size in millimeters.

    Returns:
        Mapping ``{parent_id: (min_cells, target_cells, max_cells)}`` where each
        tuple is the sum of all embedded closets under that parent.
    """
    totals: dict[str, tuple[int, int, int]] = {}
    for closet in floor.embedded_closets:
        min_cells = _embedded_closet_min_area_cells(closet, minor_grid)
        target_cells = _embedded_closet_target_area_cells(closet, minor_grid)
        max_cells = _embedded_closet_max_area_cells(closet, minor_grid)
        current = totals.get(closet.parent_id, (0, 0, 0))
        totals[closet.parent_id] = (
            current[0] + min_cells,
            current[1] + target_cells,
            current[2] + max_cells,
        )
    return totals


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
        embedded_area_by_parent = _embedded_closet_area_adjustments(floor, spec.grid.minor)
        for space in floor.spaces:
            if space.type == "closet":
                # Closets are modelled as embedded bedroom features, not independent solver entities.
                continue
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
            embedded_min_cells, embedded_target_cells, embedded_max_cells = embedded_area_by_parent.get(
                space.id, (0, 0, 0)
            )
            effective_min_area_cells = _min_area_cells(space, spec.grid.minor) + embedded_min_cells
            ctx.model.Add(area_sum >= effective_min_area_cells)
            if space.type == "hall":
                ctx.hall_area_penalties.append(area_sum)

            target_area_cells = _target_area_cells(space, spec.grid.minor)
            if target_area_cells is not None or embedded_target_cells > 0:
                effective_target_cells = (target_area_cells or 0) + embedded_target_cells
                shortfall = ctx.model.NewIntVar(
                    0,
                    ctx.max_area * component_count,
                    f"{_slug(floor_id)}_{_slug(space.id)}_area_shortfall",
                )
                ctx.model.Add(shortfall >= effective_target_cells - area_sum)
                ctx.target_shortfalls.append((shortfall, _shortfall_weight(space.type)))

                overshoot = ctx.model.NewIntVar(
                    0,
                    ctx.max_area * component_count,
                    f"{_slug(floor_id)}_{_slug(space.id)}_area_overshoot",
                )
                ctx.model.Add(overshoot >= area_sum - effective_target_cells)
                ctx.target_overshoots.append((overshoot, _overshoot_weight(space.type)))

            max_area_cells = _max_area_cells(space, spec.grid.minor)
            if max_area_cells is not None:
                ctx.model.Add(area_sum <= max_area_cells + embedded_max_cells)

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
