from __future__ import annotations

from typing import TYPE_CHECKING

from plan_engine.constants import (
    CIRCULATION_SPACE_TYPES,
    TOILET_SPACE_TYPES,
    WALK_IN_CLOSET_SPACE_TYPES,
    WET_CORE_SPACE_TYPES,
    WET_SPACE_TYPES,
)
from plan_engine.solver.constraints import touching_constraint
from plan_engine.solver.rect_var import _slug

if TYPE_CHECKING:
    from ortools.sat.python import cp_model

    from plan_engine.models import PlanSpec
    from plan_engine.solver.workflow_context import SolveContext


def add_bath_wash_adjacency_constraints(spec: PlanSpec, ctx: SolveContext) -> None:
    """Require each bath to touch a washroom and each shower to touch a washstand.

    Args:
        spec: Parsed plan specification that defines floor spaces.
        ctx: Mutable solve context that owns CP-SAT variables and model.

    Returns:
        None. Constraints are added directly to ``ctx.model``.

    Raises:
        ValueError: If a floor defines bath without washroom, or shower without washstand.
    """
    for floor_id, floor in spec.floors.items():
        bath_ids = [space.id for space in floor.spaces if space.type == "bath"]
        if bath_ids:
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

        shower_ids = [space.id for space in floor.spaces if space.type == "shower"]
        if shower_ids:
            washstand_ids = [space.id for space in floor.spaces if space.type == "washstand"]
            if not washstand_ids:
                raise ValueError(f"floor {floor_id} has shower but no washstand")

            for shower_id in shower_ids:
                touch_vars: list[cp_model.IntVar] = []
                for ws_id in washstand_ids:
                    touch_vars.append(
                        touching_constraint(
                            model=ctx.model,
                            rects_a=ctx.placements[floor_id][shower_id],
                            rects_b=ctx.placements[floor_id][ws_id],
                            max_w=ctx.envelope_w_cells,
                            max_h=ctx.envelope_h_cells,
                            prefix=f"{_slug(floor_id)}_shower_ws_{_slug(shower_id)}_{_slug(ws_id)}",
                            required=False,
                        )
                    )
                ctx.model.AddBoolOr(touch_vars)


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
            space_id for space_id, space_type in space_type_by_id.items() if space_type in WET_CORE_SPACE_TYPES
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
            raise ValueError(f"floor {floor_id} wet core requires topology adjacency to hall/entry/stair")

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


def add_closet_parent_constraints(spec: PlanSpec, ctx: SolveContext) -> None:
    """Enforce walk-in closet (WIC) parent linkage and access constraints.

    Args:
        spec: Parsed plan specification containing WIC declarations.
        ctx: Mutable solve context carrying CP-SAT variables and placements.

    Returns:
        None. Constraints are added directly to ``ctx.model``.

    Raises:
        ValueError: If WIC declarations are inconsistent.
    """
    for floor_id, floor in spec.floors.items():
        type_by_id = {space.id: space.type for space in floor.spaces}
        stair_present = (
            ctx.stair_spec is not None
            and floor_id in ctx.floors_with_stair
            and ctx.stair_spec.id in ctx.placements[floor_id]
        )
        circulation_ids = {
            space_id for space_id, space_type in type_by_id.items() if space_type in CIRCULATION_SPACE_TYPES
        }
        if stair_present and ctx.stair_spec is not None:
            circulation_ids.add(ctx.stair_spec.id)

        declared_neighbors: dict[str, set[str]] = {space_id: set() for space_id in ctx.placements[floor_id]}
        for edge in floor.topology.adjacency:
            declared_neighbors.setdefault(edge.left_id, set()).add(edge.right_id)
            declared_neighbors.setdefault(edge.right_id, set()).add(edge.left_id)

        for space in floor.spaces:
            if space.type not in WALK_IN_CLOSET_SPACE_TYPES:
                continue
            if space.parent_id is None:
                raise ValueError(f"floor {floor_id} wic '{space.id}' requires parent_id")
            if space.parent_id not in ctx.placements[floor_id]:
                raise ValueError(f"floor {floor_id} wic '{space.id}' has unknown parent_id '{space.parent_id}'")
            parent_type = type_by_id.get(space.parent_id)
            if parent_type not in {"bedroom", "master_bedroom"}:
                raise ValueError(
                    f"floor {floor_id} wic '{space.id}' parent '{space.parent_id}' must be bedroom/master_bedroom"
                )

            parent_touch = touching_constraint(
                model=ctx.model,
                rects_a=ctx.placements[floor_id][space.id],
                rects_b=ctx.placements[floor_id][space.parent_id],
                max_w=ctx.envelope_w_cells,
                max_h=ctx.envelope_h_cells,
                prefix=f"{_slug(floor_id)}_closet_parent_{_slug(space.id)}_{_slug(space.parent_id)}",
                required=False,
            )
            ctx.model.Add(parent_touch == 1)

            neighbors = sorted(declared_neighbors.get(space.id, set()))
            if not neighbors:
                raise ValueError(
                    f"floor {floor_id} wic '{space.id}' requires declared topology access to parent/hall/entry/stair"
                )
            allowed_neighbors = circulation_ids.union({space.parent_id})
            access_touch_vars: list[cp_model.IntVar] = []
            for neighbor_id in neighbors:
                if neighbor_id not in allowed_neighbors:
                    continue
                if neighbor_id not in ctx.placements[floor_id]:
                    continue
                access_touch_vars.append(
                    touching_constraint(
                        model=ctx.model,
                        rects_a=ctx.placements[floor_id][space.id],
                        rects_b=ctx.placements[floor_id][neighbor_id],
                        max_w=ctx.envelope_w_cells,
                        max_h=ctx.envelope_h_cells,
                        prefix=(f"{_slug(floor_id)}_wic_access_{_slug(space.id)}_{_slug(neighbor_id)}"),
                        required=False,
                    )
                )
            if not access_touch_vars:
                raise ValueError(
                    f"floor {floor_id} wic '{space.id}' has no valid access topology target "
                    "(expected parent/hall/entry/stair)"
                )
            ctx.model.AddBoolOr(access_touch_vars)
