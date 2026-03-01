from __future__ import annotations

from typing import TYPE_CHECKING

from plan_engine.constants import (
    EDGE_NAMES,
    WET_SPACE_TYPES,
    is_indoor_space_type,
)
from plan_engine.solver.constraints import (
    edge_touch_constraint,
    enforce_internal_portal_edge,
    enforce_non_adjacent,
    touching_constraint,
)
from plan_engine.solver.rect_var import (
    RectVar,
    _slug,
)
from plan_engine.solver.space_specs import (
    _north_preference_weight,
    _south_preference_weight,
)
from plan_engine.stair_logic import stair_portal_for_floor

if TYPE_CHECKING:
    from ortools.sat.python import cp_model

    from plan_engine.models import PlanSpec
    from plan_engine.solver.workflow_context import SolveContext


def resolve_north_south_edges(north: str) -> tuple[str, str]:
    """Resolve envelope north/south edges from ``site.north`` token.

    Args:
        north: Cardinal north token from spec/site, one of
            ``top``, ``right``, ``bottom``, ``left``.

    Returns:
        Tuple ``(north_edge, south_edge)`` in envelope edge names.

    Raises:
        ValueError: If ``north`` is not a supported edge token.
    """
    normalized = north.strip().lower()
    if normalized not in EDGE_NAMES:
        raise ValueError(f"unsupported site.north '{north}'; expected one of {sorted(EDGE_NAMES)}")

    mapping = {
        "top": ("top", "bottom"),
        "right": ("right", "left"),
        "bottom": ("bottom", "top"),
        "left": ("left", "right"),
    }
    return mapping[normalized]


def _space_edge_touch_bool(
    model: cp_model.CpModel,
    rects: list[RectVar],
    edge: str,
    envelope_w_cells: int,
    envelope_h_cells: int,
    prefix: str,
) -> cp_model.IntVar:
    """Build a boolean indicating whether a space touches a given envelope edge.

    Args:
        model: CP-SAT model receiving helper constraints.
        rects: Rectangle components that compose one logical space.
        edge: Envelope edge name (``left/right/top/bottom``).
        envelope_w_cells: Floor envelope width in cell units.
        envelope_h_cells: Floor envelope height in cell units.
        prefix: Variable-name prefix for generated booleans.

    Returns:
        Bool-var equal to 1 when any component rectangle touches ``edge``.

    Raises:
        ValueError: If ``edge`` is not supported.
    """
    if edge not in EDGE_NAMES:
        raise ValueError(f"unsupported envelope edge '{edge}'")

    component_touches: list[cp_model.IntVar] = []
    for index, rect in enumerate(rects):
        touch = model.NewBoolVar(f"{prefix}_{edge}_touch_comp_{index}")
        component_touches.append(touch)
        if edge == "left":
            model.Add(rect.x == 0).OnlyEnforceIf(touch)
            model.Add(rect.x != 0).OnlyEnforceIf(touch.Not())
        elif edge == "right":
            model.Add(rect.x_end == envelope_w_cells).OnlyEnforceIf(touch)
            model.Add(rect.x_end != envelope_w_cells).OnlyEnforceIf(touch.Not())
        elif edge == "top":
            model.Add(rect.y == 0).OnlyEnforceIf(touch)
            model.Add(rect.y != 0).OnlyEnforceIf(touch.Not())
        elif edge == "bottom":
            model.Add(rect.y_end == envelope_h_cells).OnlyEnforceIf(touch)
            model.Add(rect.y_end != envelope_h_cells).OnlyEnforceIf(touch.Not())

    touches_edge = model.NewBoolVar(f"{prefix}_{edge}_touch")
    model.AddMaxEquality(touches_edge, component_touches)
    return touches_edge


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


def add_stair_connection_constraints(ctx: SolveContext) -> None:
    """Enforce stair-to-hall portal edge connectivity."""
    if ctx.stair_spec is None:
        return
    min_components_by_type = {
        "straight": 1,
        "L_landing": 3,
        "U_turn": 3,
    }
    for floor_id, hall_id in ctx.stair_spec.connects.items():
        if floor_id not in ctx.placements:
            raise ValueError(f"stair connects references unknown floor '{floor_id}'")
        if ctx.stair_spec.id not in ctx.placements[floor_id]:
            raise ValueError(f"stair '{ctx.stair_spec.id}' is missing on floor '{floor_id}'")
        if hall_id not in ctx.placements[floor_id]:
            raise ValueError(f"stair connect hall '{hall_id}' is missing on floor '{floor_id}'")
        stair_rects = ctx.placements[floor_id][ctx.stair_spec.id]
        min_components = min_components_by_type.get(ctx.stair_spec.type)
        if min_components is None:
            raise ValueError(f"unsupported stair type '{ctx.stair_spec.type}'")
        if len(stair_rects) < min_components:
            raise ValueError(
                f"stair '{ctx.stair_spec.id}' on floor '{floor_id}' has {len(stair_rects)} components, "
                f"expected at least {min_components} for type '{ctx.stair_spec.type}'"
            )
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


def add_orientation_preference_constraints(spec: PlanSpec, ctx: SolveContext) -> None:
    """Add soft orientation penalties derived from ``site.north``.

    This function creates one soft penalty boolean per eligible space:
    - major rooms (`ldk`/`bedroom`/`master_bedroom`) prefer south edge touch
    - service rooms (`washroom`/`bath`/`toilet`/`wc`/`storage`) prefer north edge touch

    Args:
        spec: Parsed plan specification.
        ctx: Mutable solve context holding placements and objective accumulators.

    Returns:
        None. Soft-penalty terms are appended to ``ctx.orientation_soft_penalties``.
    """
    north_edge, south_edge = resolve_north_south_edges(spec.site.north)
    for floor_id, floor in spec.floors.items():
        for space in floor.spaces:
            rects = ctx.placements[floor_id].get(space.id)
            if not rects:
                continue

            south_weight = _south_preference_weight(space.type)
            if south_weight > 0:
                south_touch = _space_edge_touch_bool(
                    model=ctx.model,
                    rects=rects,
                    edge=south_edge,
                    envelope_w_cells=ctx.envelope_w_cells,
                    envelope_h_cells=ctx.envelope_h_cells,
                    prefix=f"{_slug(floor_id)}_{_slug(space.id)}",
                )
                south_missing = ctx.model.NewBoolVar(f"{_slug(floor_id)}_{_slug(space.id)}_miss_south_pref")
                ctx.model.Add(south_missing + south_touch == 1)
                ctx.orientation_soft_penalties.append((south_missing, south_weight))

            north_weight = _north_preference_weight(space.type)
            if north_weight > 0:
                north_touch = _space_edge_touch_bool(
                    model=ctx.model,
                    rects=rects,
                    edge=north_edge,
                    envelope_w_cells=ctx.envelope_w_cells,
                    envelope_h_cells=ctx.envelope_h_cells,
                    prefix=f"{_slug(floor_id)}_{_slug(space.id)}",
                )
                north_missing = ctx.model.NewBoolVar(f"{_slug(floor_id)}_{_slug(space.id)}_miss_north_pref")
                ctx.model.Add(north_missing + north_touch == 1)
                ctx.orientation_soft_penalties.append((north_missing, north_weight))


def build_objective(ctx: SolveContext) -> None:
    """Assemble and minimize the weighted objective function."""
    objective_terms = [50 * v for v in ctx.major_room_alignment_penalties]
    objective_terms.extend(weight * var for var, weight in ctx.target_shortfalls)
    objective_terms.extend(weight * var for var, weight in ctx.target_overshoots)
    objective_terms.extend(12 * v for v in ctx.shape_balance_penalties)
    objective_terms.extend(8 * v for v in ctx.floor_compactness_terms)
    objective_terms.extend(10 * v for v in ctx.hall_area_penalties)
    objective_terms.extend(weight * var for var, weight in ctx.topology_soft_penalties)
    objective_terms.extend(weight * var for var, weight in ctx.orientation_soft_penalties)
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
        ("bedroom", "wic"),
        ("hall", "master_bedroom"),
        ("hall", "wic"),
        ("hall", "storage"),
        ("master_bedroom", "storage"),
        ("master_bedroom", "wic"),
    }:
        return "preferred"
    return "required"
