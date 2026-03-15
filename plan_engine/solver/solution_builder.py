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

        buildable_mask_rects = [Rect(x=mask.x, y=mask.y, w=mask.w, h=mask.h) for mask in floor.buildable_mask]
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


def compute_door_segments(
    solved_spaces: dict[str, SpaceGeometry],
    floor_topology: list[tuple[str, str]],
) -> dict[frozenset[str], tuple[tuple[int, int], tuple[int, int]]]:
    """Compute exact door segment positions for each door-eligible topology edge.

    Args:
        solved_spaces: Solved spaces keyed by id.
        floor_topology: Topology adjacency pairs.

    Returns:
        Mapping of ``frozenset({space_a_id, space_b_id})`` to the longest
        shared edge segment ``((x1, y1), (x2, y2))`` for each pair that
        warrants an interior door.
    """
    result: dict[frozenset[str], tuple[tuple[int, int], tuple[int, int]]] = {}
    for left_id, right_id in floor_topology:
        left_space = solved_spaces.get(left_id)
        right_space = solved_spaces.get(right_id)
        if left_space is None or right_space is None:
            continue
        if not left_space.rects or not right_space.rects:
            continue
        if not should_draw_interior_door(left_space.type, right_space.type):
            continue
        best_segment: tuple[tuple[int, int], tuple[int, int]] | None = None
        best_length = 0
        for rect_a in left_space.rects:
            for rect_b in right_space.rects:
                segment = rect_a.shared_edge_segment(rect_b)
                if segment is None:
                    continue
                length = abs(segment[1][0] - segment[0][0]) + abs(segment[1][1] - segment[0][1])
                if length > best_length:
                    best_length = length
                    best_segment = segment
        if best_segment is not None:
            pair_key = frozenset((left_id, right_id))
            result[pair_key] = best_segment
    return result


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

    door_segments = compute_door_segments(solved_spaces, floor_topology)

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
            door_segments=door_segments,
        )
        closet_blocked = _closet_blocked_exterior_segments(closet_rect, building_rect)
        geometries.append(
            EmbeddedClosetGeometry(
                id=closet.id,
                parent_id=closet.parent_id,
                rect=closet_rect,
                blocked_exterior_segments=closet_blocked,
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
    door_segments: dict[frozenset[str], tuple[tuple[int, int], tuple[int, int]]] | None = None,
) -> Rect:
    """Fit one rectangular closet strip inside the host room using the short-wall-span rule.

    CL always spans the full short side of the parent room, cut from one end
    of the long axis.  The remaining bedroom is always rectangular.

    Falls back to legacy placement when short-wall context is unavailable.
    """
    if building_rect is not None and host_id is not None and door_segments is not None:
        short_side = min(host.w, host.h)
        depth_mm = depth_cells_candidates[0] * minor_grid if depth_cells_candidates else 2 * minor_grid

        # Overshoot cap: if short_side * depth > 2 * target, reduce depth
        if short_side * depth_mm > 2 * target_area_mm2:
            reduced = math.ceil(target_area_mm2 / short_side / minor_grid) * minor_grid
            depth_mm = max(minor_grid, reduced)

        wall_name, is_long_side_fallback = _pick_closet_wall(
            host=host,
            building_rect=building_rect,
            door_segments=door_segments,
            host_id=host_id,
            floor_topology=floor_topology or [],
            depth_mm=depth_mm,
        )

        # Verify depth fits within the room along the long axis
        if wall_name in ("top", "bottom") and depth_mm > host.h:
            depth_mm = host.h
        elif wall_name in ("left", "right") and depth_mm > host.w:
            depth_mm = host.w

        if is_long_side_fallback:
            # Partial span: size CL to target area, not full wall length
            span_mm = _ceil_to_mm_cells(target_area_mm2 / depth_mm, minor_grid)
            # Clamp to wall length
            wall_length = host.w if wall_name in ("top", "bottom") else host.h
            span_mm = min(span_mm, wall_length)
        else:
            span_mm = short_side

        return _place_closet_on_wall(host, wall_name, depth_mm, span_mm)

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


def _closet_blocked_exterior_segments(
    closet_rect: Rect,
    building_rect: Rect,
) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    """Return exterior wall segments occupied by the closet rect.

    An exterior segment is an edge of the closet rect that coincides with the
    building footprint boundary.
    """
    segments: list[tuple[tuple[int, int], tuple[int, int]]] = []
    if closet_rect.y == building_rect.y:
        segments.append(((closet_rect.x, closet_rect.y), (closet_rect.x2, closet_rect.y)))
    if closet_rect.y2 == building_rect.y2:
        segments.append(((closet_rect.x, closet_rect.y2), (closet_rect.x2, closet_rect.y2)))
    if closet_rect.x == building_rect.x:
        segments.append(((closet_rect.x, closet_rect.y), (closet_rect.x, closet_rect.y2)))
    if closet_rect.x2 == building_rect.x2:
        segments.append(((closet_rect.x2, closet_rect.y), (closet_rect.x2, closet_rect.y2)))
    return segments


def _would_block_all_windows(
    host: Rect,
    wall_name: str,
    building_rect: Rect,
) -> bool:
    """Return True if placing CL on *wall_name* would block all exterior window segments.

    This checks whether the parent room has any exterior wall on a side OTHER
    than ``wall_name``.  If not, covering ``wall_name`` eliminates all possible
    window positions.
    """
    other_exterior = {
        "top": host.y == building_rect.y,
        "bottom": host.y2 == building_rect.y2,
        "left": host.x == building_rect.x,
        "right": host.x2 == building_rect.x2,
    }
    # Remove the wall we're considering placing CL on
    other_exterior.pop(wall_name, None)
    return not any(other_exterior.values())


def _pick_closet_wall(
    host: Rect,
    building_rect: Rect,
    door_segments: dict[frozenset[str], tuple[tuple[int, int], tuple[int, int]]],
    host_id: str,
    floor_topology: list[tuple[str, str]],
    depth_mm: int = 910,
) -> tuple[str, bool]:
    """Pick which wall to place the closet on using the short-wall-span rule.

    For a non-square room, CL candidates are the two walls at the ends of the
    long axis (these have length == short side).  When all short-side candidates
    would block every exterior window segment, long-side walls are added as
    fallback candidates so that the exterior wall is preserved for windows.

    Scoring per candidate: ``(blocks_door, kills_all_windows, is_exterior)``.

    1. Avoid walls where the CL strip would block any door (highest priority).
    2. Preserve windows: never choose a wall that eliminates all window
       segments when an alternative exists.
    3. Among remaining, prefer interior over exterior.

    For a near-square room, consider all four walls with the same scoring.

    Args:
        host: Parent room rectangle.
        building_rect: Building footprint bounding rect.
        door_segments: Pre-computed door segments from ``compute_door_segments()``.
        host_id: Parent room id.
        floor_topology: Floor topology adjacency pairs.
        depth_mm: CL strip depth in millimeters (used for overlap simulation).

    Returns:
        Tuple of (wall_name, is_long_side_fallback).
        ``is_long_side_fallback`` is True when the selected wall is a long-side
        wall chosen to preserve windows (CL should use partial span).
    """
    if host.w > host.h:
        short_side_walls = ["left", "right"]
        long_side_walls = ["top", "bottom"]
    elif host.h > host.w:
        short_side_walls = ["top", "bottom"]
        long_side_walls = ["left", "right"]
    else:
        short_side_walls = ["top", "bottom", "left", "right"]
        long_side_walls = []

    is_exterior = {
        "top": host.y == building_rect.y,
        "bottom": host.y2 == building_rect.y2,
        "left": host.x == building_rect.x,
        "right": host.x2 == building_rect.x2,
    }

    short_side = min(host.w, host.h)
    host_door_segs = [seg for key, seg in door_segments.items() if host_id in key]

    def _cl_blocks_door(wall_name: str, span: int) -> int:
        """Return 1 if the CL strip on *wall_name* would overlap any door."""
        cl = _place_closet_on_wall(host, wall_name, depth_mm, span)
        for (sx1, sy1), (sx2, sy2) in host_door_segs:
            if sx1 == sx2 and cl.x <= sx1 <= cl.x2 and cl.y < max(sy1, sy2) and cl.y2 > min(sy1, sy2):
                return 1
            if sy1 == sy2 and cl.y <= sy1 <= cl.y2 and cl.x < max(sx1, sx2) and cl.x2 > min(sx1, sx2):
                return 1
        return 0

    def wall_score(wall_name: str, span: int) -> tuple[int, int, int]:
        kills = 1 if _would_block_all_windows(host, wall_name, building_rect) else 0
        return (_cl_blocks_door(wall_name, span), kills, 1 if is_exterior[wall_name] else 0)

    # Score short-side candidates first
    short_scored = [(wall_score(w, short_side), w) for w in short_side_walls]
    short_scored.sort(key=lambda t: t[0])
    best_short = short_scored[0]

    # If the best short-side candidate would kill all windows, add long sides
    best_short_kills = best_short[0][1] == 1
    if best_short_kills and long_side_walls:
        candidates = short_side_walls + long_side_walls
        scored = [(wall_score(w, short_side), w) for w in candidates]
        scored.sort(key=lambda t: t[0])
        best_wall = scored[0][1]
        is_fallback = best_wall in long_side_walls
    else:
        best_wall = best_short[1]
        is_fallback = False

    return best_wall, is_fallback


def _place_closet_on_wall(
    host: Rect,
    wall_name: str,
    depth_mm: int,
    span_mm: int,
) -> Rect:
    """Place a closet strip on the named wall.

    The CL rect spans ``span_mm`` along the wall and ``depth_mm`` mm cut
    from it.  For short-side placement ``span_mm`` equals the full short
    side.  For long-side fallback ``span_mm`` may be smaller than the wall
    length (partial coverage).

    The strip is anchored at the "first" corner of the wall (top-left for
    top/left, bottom-left for bottom, top-right for right).

    Args:
        host: Parent room rectangle.
        wall_name: Target wall (``'top'``/``'bottom'``/``'left'``/``'right'``).
        depth_mm: Closet depth in millimeters.
        span_mm: Length of the CL strip along the wall.

    Returns:
        CL rectangle.
    """
    if wall_name == "top":
        return Rect(host.x, host.y, span_mm, depth_mm)
    if wall_name == "bottom":
        return Rect(host.x, host.y2 - depth_mm, span_mm, depth_mm)
    if wall_name == "left":
        return Rect(host.x, host.y, depth_mm, span_mm)
    # right
    return Rect(host.x2 - depth_mm, host.y, depth_mm, span_mm)
