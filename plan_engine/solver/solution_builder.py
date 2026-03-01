from __future__ import annotations

import math
from typing import TYPE_CHECKING

from plan_engine.constants import cells_to_mm, should_draw_interior_door, tatami_to_cells
from plan_engine.models import (
    EmbeddedClosetGeometry,
    EmbeddedClosetSpec,
    FloorSolution,
    PlanSolution,
    PlanSpec,
    Rect,
    SpaceGeometry,
    StairGeometry,
    StairSpec,
)
from plan_engine.stair_logic import stair_portal_for_floor
from plan_engine.structural import build_structure_report, extract_solution_walls

if TYPE_CHECKING:
    from ortools.sat.python import cp_model

    from plan_engine.solver.rect_var import RectVar, StairFootprint


def build_solution(
    solver: cp_model.CpSolver,
    spec: PlanSpec,
    placements: dict[str, dict[str, list[RectVar]]],
    stair_spec: StairSpec | None,
    stair_footprint: StairFootprint | None,
    floor_rank: dict[str, int],
    ordered_floors: list[str],
) -> PlanSolution:
    """Convert solved CP-SAT variables into a PlanSolution with structural diagnostics.

    Args:
        solver: CP-SAT solver containing selected variable values.
        spec: Parsed plan specification.
        placements: Per-floor/per-entity rectangle variable sets.
        stair_spec: Shared stair specification, when present.
        stair_footprint: Stair footprint metadata in grid cells.
        floor_rank: Floor index mapping for portal direction resolution.
        ordered_floors: Floor IDs in vertical order.

    Returns:
        Immutable solved plan including extracted wall segments and
        structural-report metrics.
    """
    floor_solutions: dict[str, FloorSolution] = {}
    for floor_id, floor in spec.floors.items():
        solved_spaces: dict[str, SpaceGeometry] = {}
        for space in floor.spaces:
            if space.type == "closet":
                continue
            rects = [
                Rect(
                    x=cells_to_mm(solver.Value(rect.x), spec.grid.minor),
                    y=cells_to_mm(solver.Value(rect.y), spec.grid.minor),
                    w=cells_to_mm(solver.Value(rect.w), spec.grid.minor),
                    h=cells_to_mm(solver.Value(rect.h), spec.grid.minor),
                )
                for rect in placements[floor_id][space.id]
            ]
            solved_spaces[space.id] = SpaceGeometry(
                id=space.id,
                type=space.type,
                rects=rects,
                space_class=space.space_class,
                parent_id=space.parent_id,
            )
        floor_topology_tuples = [edge.to_tuple() for edge in floor.topology.adjacency]
        embedded_closets = _build_embedded_closet_geometries(
            closet_specs=floor.embedded_closets,
            solved_spaces=solved_spaces,
            minor_grid=spec.grid.minor,
            floor_topology=floor_topology_tuples,
        )

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
            portal = stair_portal_for_floor(
                stair_type=stair_spec.type,
                floor_index=floor_rank[floor_id],
                floor_count=len(ordered_floors),
                component_count=len(stair_components),
            )
            if portal.component_index < 0 or portal.component_index >= len(stair_components):
                raise ValueError(
                    f"stair '{stair_spec.id}' portal component {portal.component_index} is out of range "
                    f"for floor '{floor_id}' ({len(stair_components)} components)"
                )
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
                floor_height=stair_spec.floor_height,
                riser_count=stair_footprint.riser_count,
                tread_count=stair_footprint.tread_count,
                riser_mm=stair_footprint.riser_mm,
                tread_mm=stair_footprint.tread_mm,
                landing_size=stair_footprint.landing_mm,
                connects=stair_spec.connects,
                portal_component=portal.component_index,
                portal_edge=portal.edge,
            )

        buildable_mask_rects = [
            Rect(x=mask.x, y=mask.y, w=mask.w, h=mask.h)
            for mask in floor.buildable_mask
        ]
        if not buildable_mask_rects:
            buildable_mask_rects = [Rect(x=0, y=0, w=spec.site.envelope.width, h=spec.site.envelope.depth)]
        indoor_buildable_area_mm2 = sum(rect.area for rect in buildable_mask_rects)

        floor_solutions[floor_id] = FloorSolution(
            id=floor_id,
            spaces=solved_spaces,
            embedded_closets=embedded_closets,
            stair=stair_geometry,
            topology=floor_topology_tuples,
            buildable_mask=buildable_mask_rects,
            indoor_buildable_area_mm2=indoor_buildable_area_mm2,
        )

    base_solution = PlanSolution(
        units=spec.units,
        grid=spec.grid,
        envelope=spec.site.envelope,
        north=spec.site.north,
        floors=floor_solutions,
    )
    walls_by_floor = extract_solution_walls(base_solution)
    structure_report = build_structure_report(
        solution=base_solution,
        walls_by_floor=walls_by_floor,
        direct_below_target=0.5,
        wall_balance_target=0.5,
    )
    return PlanSolution(
        units=spec.units,
        grid=spec.grid,
        envelope=spec.site.envelope,
        north=spec.site.north,
        floors=floor_solutions,
        walls=walls_by_floor,
        structure_report=structure_report,
    )


def _build_embedded_closet_geometries(
    closet_specs: list[EmbeddedClosetSpec],
    solved_spaces: dict[str, SpaceGeometry],
    minor_grid: int,
    floor_topology: list[tuple[str, str]] | None = None,
) -> list[EmbeddedClosetGeometry]:
    """Create deterministic in-room closet rectangles for rendering/validation.

    Args:
        closet_specs: Embedded closet declarations for one floor.
        solved_spaces: Solved spaces keyed by id.
        minor_grid: Minor grid size in millimeters.
        floor_topology: Floor topology adjacency pairs for wall classification.

    Returns:
        Embedded closet geometries located inside their parent room.
    """
    building_rect = _compute_building_rect(solved_spaces)
    if floor_topology is None:
        floor_topology = []

    geometries: list[EmbeddedClosetGeometry] = []
    for closet in closet_specs:
        parent = solved_spaces.get(closet.parent_id)
        if parent is None or not parent.rects:
            continue
        host = max(parent.rects, key=lambda rect: rect.area)
        target_cells = _embedded_closet_target_cells(closet, minor_grid)
        target_area_mm2 = target_cells * (minor_grid * minor_grid)
        depth_cells_candidates = _depth_candidates(
            requested_depth_mm=closet.depth_mm,
            host=host,
            minor_grid=minor_grid,
        )
        closet_rect = _fit_closet_strip(
            host=host,
            target_area_mm2=target_area_mm2,
            depth_cells_candidates=depth_cells_candidates,
            minor_grid=minor_grid,
            building_rect=building_rect,
            floor_topology=floor_topology,
            solved_spaces=solved_spaces,
            host_id=closet.parent_id,
            host_type=parent.type,
        )
        geometries.append(
            EmbeddedClosetGeometry(
                id=closet.id,
                parent_id=closet.parent_id,
                rect=closet_rect,
            )
        )
    return geometries


def _embedded_closet_target_cells(closet: EmbeddedClosetSpec, minor_grid: int) -> int:
    """Resolve closet target area in cells from explicit or default tatami values."""
    if closet.area.target_tatami is not None:
        return max(1, tatami_to_cells(closet.area.target_tatami, minor_grid))
    if closet.area.min_tatami is not None:
        return max(1, tatami_to_cells(closet.area.min_tatami, minor_grid))
    return max(1, tatami_to_cells(1.0, minor_grid))


def _depth_candidates(requested_depth_mm: int | None, host: Rect, minor_grid: int) -> list[int]:
    """Return candidate closet depths in cells, ordered by preference."""
    candidates: list[int] = []
    if requested_depth_mm is not None and requested_depth_mm % minor_grid == 0:
        requested_cells = max(1, requested_depth_mm // minor_grid)
        candidates.append(requested_cells)
    candidates.extend([2, 1, 3, 4])
    unique: list[int] = []
    max_dim_cells = max(1, max(host.w, host.h) // minor_grid)
    for depth in candidates:
        if depth <= 0 or depth > max_dim_cells:
            continue
        if depth not in unique:
            unique.append(depth)
    return unique or [1]


def _fit_closet_strip(
    host: Rect,
    target_area_mm2: int,
    depth_cells_candidates: list[int],
    minor_grid: int,
    building_rect: Rect | None = None,
    floor_topology: list[tuple[str, str]] | None = None,
    solved_spaces: dict[str, SpaceGeometry] | None = None,
    host_id: str | None = None,
    host_type: str | None = None,
) -> Rect:
    """Fit one rectangular closet strip inside the host room.

    When wall-classification context is available, uses wall-aware placement
    that avoids exterior (window) and door walls. Falls back to legacy
    area-overshoot minimization when context is missing.
    """
    if building_rect is not None and host_id is not None and host_type is not None:
        walls = _classify_walls(
            host=host,
            building_rect=building_rect,
            host_id=host_id,
            host_type=host_type,
            floor_topology=floor_topology or [],
            solved_spaces=solved_spaces or {},
        )
        result = _select_closet_wall(
            walls=walls,
            host=host,
            depth_cells_candidates=depth_cells_candidates,
            minor_grid=minor_grid,
            target_area_mm2=target_area_mm2,
        )
        if result is not None:
            return result

    return _fit_closet_strip_legacy(host, target_area_mm2, depth_cells_candidates, minor_grid)


def _fit_closet_strip_legacy(
    host: Rect,
    target_area_mm2: int,
    depth_cells_candidates: list[int],
    minor_grid: int,
) -> Rect:
    """Legacy closet placement: tries top-left then right-edge, minimizes overshoot."""
    best: tuple[int, Rect] | None = None
    for depth_cells in depth_cells_candidates:
        depth_mm = depth_cells * minor_grid
        if depth_mm <= 0:
            continue

        if host.h >= depth_mm:
            width_mm = min(host.w, _ceil_to_mm_cells(target_area_mm2 / depth_mm, minor_grid))
            if width_mm > 0:
                candidate = Rect(x=host.x, y=host.y, w=width_mm, h=depth_mm)
                overshoot = max(0, candidate.area - target_area_mm2)
                if best is None or overshoot < best[0]:
                    best = (overshoot, candidate)

        if host.w >= depth_mm:
            height_mm = min(host.h, _ceil_to_mm_cells(target_area_mm2 / depth_mm, minor_grid))
            if height_mm > 0:
                candidate = Rect(x=host.x2 - depth_mm, y=host.y, w=depth_mm, h=height_mm)
                overshoot = max(0, candidate.area - target_area_mm2)
                if best is None or overshoot < best[0]:
                    best = (overshoot, candidate)

    if best is not None:
        return best[1]
    fallback_depth = min(host.h, minor_grid)
    fallback_width = min(host.w, minor_grid)
    return Rect(x=host.x, y=host.y, w=fallback_width, h=fallback_depth)


def _ceil_to_mm_cells(raw_mm: float, minor_grid: int) -> int:
    """Round up a millimeter value to a positive minor-grid multiple."""
    return max(minor_grid, int(math.ceil(raw_mm / minor_grid) * minor_grid))


# ---------------------------------------------------------------------------
# Wall-aware closet placement helpers
# ---------------------------------------------------------------------------


def _compute_building_rect(solved_spaces: dict[str, SpaceGeometry]) -> Rect:
    """Compute bounding rect of all solved space rects (building footprint)."""
    all_rects = [rect for space in solved_spaces.values() for rect in space.rects]
    if not all_rects:
        return Rect(0, 0, 0, 0)
    min_x = min(r.x for r in all_rects)
    min_y = min(r.y for r in all_rects)
    max_x = max(r.x2 for r in all_rects)
    max_y = max(r.y2 for r in all_rects)
    return Rect(min_x, min_y, max_x - min_x, max_y - min_y)


def _classify_walls(
    host: Rect,
    building_rect: Rect,
    host_id: str,
    host_type: str,
    floor_topology: list[tuple[str, str]],
    solved_spaces: dict[str, SpaceGeometry],
) -> dict[str, str]:
    """Classify each wall of the host room as free/exterior/door/both.

    Args:
        host: Parent room rectangle.
        building_rect: Building footprint bounding rect.
        host_id: Parent room id.
        host_type: Parent room space type.
        floor_topology: Topology adjacency pairs.
        solved_spaces: All solved spaces on this floor.

    Returns:
        Mapping ``{top, bottom, left, right}`` to classification string.
    """
    is_exterior = {
        "top": host.y == building_rect.y,
        "bottom": host.y2 == building_rect.y2,
        "left": host.x == building_rect.x,
        "right": host.x2 == building_rect.x2,
    }

    has_door: dict[str, bool] = {"top": False, "bottom": False, "left": False, "right": False}
    for left_id, right_id in floor_topology:
        neighbor_id = right_id if left_id == host_id else (left_id if right_id == host_id else None)
        if neighbor_id is None or neighbor_id not in solved_spaces:
            continue
        neighbor = solved_spaces[neighbor_id]
        if not should_draw_interior_door(host_type, neighbor.type):
            continue
        for wall_name in _neighbor_touching_walls(host, neighbor.rects):
            has_door[wall_name] = True

    result: dict[str, str] = {}
    for wall_name in ("top", "bottom", "left", "right"):
        ext = is_exterior[wall_name]
        door = has_door[wall_name]
        if ext and door:
            result[wall_name] = "both"
        elif ext:
            result[wall_name] = "exterior"
        elif door:
            result[wall_name] = "door"
        else:
            result[wall_name] = "free"
    return result


def _neighbor_touching_walls(host: Rect, neighbor_rects: list[Rect]) -> list[str]:
    """Return which walls of host are touched by any neighbor rect with positive overlap."""
    walls: list[str] = []
    for nr in neighbor_rects:
        if nr.y2 == host.y and _overlap_len(nr.x, nr.x2, host.x, host.x2) > 0 and "top" not in walls:
            walls.append("top")
        if nr.y == host.y2 and _overlap_len(nr.x, nr.x2, host.x, host.x2) > 0 and "bottom" not in walls:
            walls.append("bottom")
        if nr.x2 == host.x and _overlap_len(nr.y, nr.y2, host.y, host.y2) > 0 and "left" not in walls:
            walls.append("left")
        if nr.x == host.x2 and _overlap_len(nr.y, nr.y2, host.y, host.y2) > 0 and "right" not in walls:
            walls.append("right")
    return walls


def _overlap_len(a1: int, a2: int, b1: int, b2: int) -> int:
    """Return overlap length of two 1D intervals [a1,a2] and [b1,b2]."""
    return max(0, min(a2, b2) - max(a1, b1))


def _span_wall(host: Rect, wall_name: str, depth_mm: int) -> Rect | None:
    """Place a closet spanning the full length of the named wall at given depth."""
    if wall_name == "top" and host.h >= depth_mm:
        return Rect(host.x, host.y, host.w, depth_mm)
    if wall_name == "bottom" and host.h >= depth_mm:
        return Rect(host.x, host.y2 - depth_mm, host.w, depth_mm)
    if wall_name == "left" and host.w >= depth_mm:
        return Rect(host.x, host.y, depth_mm, host.h)
    if wall_name == "right" and host.w >= depth_mm:
        return Rect(host.x2 - depth_mm, host.y, depth_mm, host.h)
    return None


def _wall_span_length(host: Rect, wall_name: str) -> int:
    """Return the length of the named wall."""
    if wall_name in ("top", "bottom"):
        return host.w
    return host.h


def _select_closet_wall(
    walls: dict[str, str],
    host: Rect,
    depth_cells_candidates: list[int],
    minor_grid: int,
    target_area_mm2: int,
) -> Rect | None:
    """Select best wall and return a closet rect, or None to fall back to legacy.

    Priority: free walls (shorter first) with full span, then partial span on
    free walls if full-span overshoots >2x, then door/exterior walls.
    """
    overshoot_cap = 2 * target_area_mm2

    # Sort free walls by span length ascending (shorter wall → closer to target area)
    free_walls = sorted(
        [name for name, cls in walls.items() if cls == "free"],
        key=lambda n: _wall_span_length(host, n),
    )
    # Try full span on free walls
    for wall_name in free_walls:
        for depth_cells in depth_cells_candidates:
            depth_mm = depth_cells * minor_grid
            rect = _span_wall(host, wall_name, depth_mm)
            if rect is None:
                continue
            if rect.area <= overshoot_cap:
                return rect
            # Over 2x cap: use partial span on this free wall
            return _partial_span_on_wall(host, wall_name, depth_mm, target_area_mm2, minor_grid)

    # No free wall: try door walls (less preferred)
    door_walls = sorted(
        [name for name, cls in walls.items() if cls == "door"],
        key=lambda n: _wall_span_length(host, n),
    )
    for wall_name in door_walls:
        for depth_cells in depth_cells_candidates:
            depth_mm = depth_cells * minor_grid
            rect = _partial_span_on_wall(host, wall_name, depth_mm, target_area_mm2, minor_grid)
            if rect is not None:
                return rect

    return None


def _partial_span_on_wall(
    host: Rect, wall_name: str, depth_mm: int, target_area_mm2: int, minor_grid: int,
) -> Rect | None:
    """Place a partial-span closet strip on the named wall, sized to approximate target area."""
    span_length = _wall_span_length(host, wall_name)
    if depth_mm <= 0 or depth_mm > (host.h if wall_name in ("top", "bottom") else host.w):
        return None

    needed_span = _ceil_to_mm_cells(target_area_mm2 / depth_mm, minor_grid)
    actual_span = min(span_length, needed_span)
    if actual_span <= 0:
        return None

    if wall_name == "top":
        return Rect(host.x, host.y, actual_span, depth_mm)
    if wall_name == "bottom":
        return Rect(host.x, host.y2 - depth_mm, actual_span, depth_mm)
    if wall_name == "left":
        return Rect(host.x, host.y, depth_mm, actual_span)
    if wall_name == "right":
        return Rect(host.x2 - depth_mm, host.y, depth_mm, actual_span)
    return None
