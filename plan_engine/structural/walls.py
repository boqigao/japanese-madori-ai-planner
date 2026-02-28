from __future__ import annotations

from collections import defaultdict

from plan_engine.constants import is_indoor_space_type
from plan_engine.models import (
    ContinuityMetrics,
    FloorStructureMetrics,
    PlanSolution,
    StructureReport,
    VerticalTransferRequirement,
    WallSegment,
)
from plan_engine.stair_logic import ordered_floor_ids

BEARING_ROLES = {"load_bearing", "candidate_bearing"}


def extract_solution_walls(solution: PlanSolution) -> dict[str, list[WallSegment]]:
    """Extract merged wall segments for each floor from solved room/stair geometry.

    The extractor works on the solved occupancy grid (minor grid cells). Each
    boundary between occupied cells and exterior becomes an exterior wall
    segment; each boundary between different occupied entities becomes an
    interior wall segment. Cell-level segments are merged into longer spans.

    Args:
        solution: Solved plan geometry.

    Returns:
        Mapping from floor id to extracted wall segments.
    """
    walls_by_floor: dict[str, list[WallSegment]] = {}
    for floor_id, _floor in solution.floors.items():
        cell_owner = _build_cell_ownership(solution=solution, floor_id=floor_id)
        raw_segments = _collect_raw_segments(
            cell_owner=cell_owner,
            width=solution.envelope.width,
            depth=solution.envelope.depth,
            minor=solution.grid.minor,
        )
        walls_by_floor[floor_id] = _build_wall_segments(
            floor_id=floor_id,
            raw_segments=raw_segments,
            major_grid=solution.grid.major,
        )
    return walls_by_floor


def build_structure_report(
    solution: PlanSolution,
    walls_by_floor: dict[str, list[WallSegment]],
    direct_below_target: float = 0.5,
    wall_balance_target: float = 0.5,
) -> StructureReport:
    """Compute structural diagnostics from extracted wall segments.

    Args:
        solution: Solved plan geometry.
        walls_by_floor: Extracted walls keyed by floor id.
        direct_below_target: Warning threshold for upper/lower wall continuity.
        wall_balance_target: Warning threshold for quadrant balance.

    Returns:
        Aggregated structure report containing floor metrics, cross-floor
        continuity, transfer requirements, and warnings.
    """
    floor_metrics: dict[str, FloorStructureMetrics] = {}
    warnings: list[str] = []

    for floor_id in ordered_floor_ids(list(solution.floors.keys())):
        walls = walls_by_floor.get(floor_id, [])
        bearing = [wall for wall in walls if wall.role in BEARING_ROLES]
        bearing_vertical = sum(wall.length_mm for wall in bearing if wall.orientation == "vertical")
        bearing_horizontal = sum(wall.length_mm for wall in bearing if wall.orientation == "horizontal")
        total_wall_length = sum(wall.length_mm for wall in walls)
        total_bearing_length = bearing_vertical + bearing_horizontal
        quadrants = _quadrant_bearing_lengths(
            walls=bearing,
            width=solution.envelope.width,
            depth=solution.envelope.depth,
        )
        balance_ratio = _balance_ratio(quadrants)
        floor_metrics[floor_id] = FloorStructureMetrics(
            floor_id=floor_id,
            total_wall_length_mm=total_wall_length,
            total_bearing_length_mm=total_bearing_length,
            bearing_vertical_mm=bearing_vertical,
            bearing_horizontal_mm=bearing_horizontal,
            quadrant_bearing_mm=quadrants,
            wall_balance_ratio=balance_ratio,
        )
        if balance_ratio is not None and balance_ratio < wall_balance_target:
            warnings.append(
                f"{floor_id}: wall-balance ratio {balance_ratio:.2f} below target {wall_balance_target:.2f}"
            )

    continuity: list[ContinuityMetrics] = []
    transfer_required: list[VerticalTransferRequirement] = []
    ordered = ordered_floor_ids(list(solution.floors.keys()))
    for index in range(1, len(ordered)):
        lower_floor_id = ordered[index - 1]
        upper_floor_id = ordered[index]
        lower_walls = [wall for wall in walls_by_floor.get(lower_floor_id, []) if wall.role in BEARING_ROLES]
        upper_walls = [wall for wall in walls_by_floor.get(upper_floor_id, []) if wall.role in BEARING_ROLES]
        for orientation in ("vertical", "horizontal"):
            lower_map = _line_interval_map(lower_walls, orientation)
            upper_segments = [wall for wall in upper_walls if wall.orientation == orientation]
            total_upper = sum(wall.length_mm for wall in upper_segments)
            supported = 0
            for wall in upper_segments:
                lower_intervals = lower_map.get(wall.line_coord_mm, [])
                overlap = _overlap_with_intervals(
                    start=wall.span_start_mm,
                    end=wall.span_end_mm,
                    intervals=lower_intervals,
                )
                supported += overlap
                unsupported = wall.length_mm - overlap
                if unsupported > 0:
                    transfer_required.append(
                        VerticalTransferRequirement(
                            upper_floor_id=upper_floor_id,
                            segment_id=wall.id,
                            orientation=wall.orientation,
                            line_coord_mm=wall.line_coord_mm,
                            span_start_mm=wall.span_start_mm,
                            span_end_mm=wall.span_end_mm,
                            unsupported_length_mm=unsupported,
                        )
                    )

            ratio = (supported / total_upper) if total_upper > 0 else None
            continuity.append(
                ContinuityMetrics(
                    lower_floor_id=lower_floor_id,
                    upper_floor_id=upper_floor_id,
                    orientation=orientation,
                    upper_bearing_length_mm=total_upper,
                    supported_length_mm=supported,
                    direct_below_ratio=ratio,
                )
            )
            if ratio is not None and ratio < direct_below_target:
                warnings.append(
                    f"{upper_floor_id}->{lower_floor_id} {orientation} direct-below ratio {ratio:.2f} below target {direct_below_target:.2f}"
                )

    if transfer_required:
        warnings.append(f"vertical transfer required on {len(transfer_required)} upper-floor bearing segments")

    assumptions = [
        "Bearing roles are heuristic proxies (not final structural certification).",
        "Role proxy: exterior walls => load_bearing, major-grid interior lines => candidate_bearing.",
        "Thresholds are advisory in this phase (warnings only).",
    ]
    return StructureReport(
        floor_metrics=floor_metrics,
        continuity_metrics=continuity,
        vertical_transfer_required=transfer_required,
        warnings=warnings,
        assumptions=assumptions,
    )


def _build_cell_ownership(solution: PlanSolution, floor_id: str) -> dict[tuple[int, int], str]:
    """Map each occupied minor-grid cell to its owning entity id.

    Args:
        solution: Solved plan geometry.
        floor_id: Floor to build ownership map for.

    Returns:
        Dictionary keyed by cell origin `(x, y)` in mm.
    """
    floor = solution.floors[floor_id]
    minor = solution.grid.minor
    owner: dict[tuple[int, int], str] = {}
    for space_id, space in floor.spaces.items():
        if not is_indoor_space_type(space.type):
            continue
        for rect in space.rects:
            for x in range(rect.x, rect.x2, minor):
                for y in range(rect.y, rect.y2, minor):
                    owner[(x, y)] = f"space:{space_id}"
    if floor.stair is not None:
        for rect in floor.stair.components:
            for x in range(rect.x, rect.x2, minor):
                for y in range(rect.y, rect.y2, minor):
                    owner[(x, y)] = f"stair:{floor.stair.id}"
    return owner


def _collect_raw_segments(
    cell_owner: dict[tuple[int, int], str],
    width: int,
    depth: int,
    minor: int,
) -> list[tuple[str, int, int, int, str]]:
    """Collect cell-level boundary segments before span merging.

    Args:
        cell_owner: Ownership map keyed by cell origin.
        width: Envelope width in mm.
        depth: Envelope depth in mm.
        minor: Minor grid size in mm.

    Returns:
        Raw segment tuples as `(orientation, line_coord, start, end, kind)`.
    """
    raw: list[tuple[str, int, int, int, str]] = []
    for (x, y), owner in cell_owner.items():
        if x == 0:
            raw.append(("vertical", x, y, y + minor, "exterior"))
        if y == 0:
            raw.append(("horizontal", y, x, x + minor, "exterior"))
        if x + minor == width:
            raw.append(("vertical", width, y, y + minor, "exterior"))
        if y + minor == depth:
            raw.append(("horizontal", depth, x, x + minor, "exterior"))

        if x + minor < width:
            right_owner = cell_owner.get((x + minor, y))
            if right_owner != owner:
                kind = "interior" if right_owner is not None else "exterior"
                raw.append(("vertical", x + minor, y, y + minor, kind))
        if y + minor < depth:
            down_owner = cell_owner.get((x, y + minor))
            if down_owner != owner:
                kind = "interior" if down_owner is not None else "exterior"
                raw.append(("horizontal", y + minor, x, x + minor, kind))
    return raw


def _build_wall_segments(
    floor_id: str,
    raw_segments: list[tuple[str, int, int, int, str]],
    major_grid: int,
) -> list[WallSegment]:
    """Merge raw segments and classify each merged span into a wall role.

    Args:
        floor_id: Floor identifier.
        raw_segments: Cell-level boundary segments.
        major_grid: Major grid size in mm.

    Returns:
        Sorted list of merged wall segments with assigned roles.
    """
    grouped: dict[tuple[str, int, str], list[tuple[int, int]]] = defaultdict(list)
    for orientation, line_coord, start, end, kind in raw_segments:
        grouped[(orientation, line_coord, kind)].append((start, end))

    walls: list[WallSegment] = []
    for (orientation, line_coord, kind), spans in grouped.items():
        merged = _merge_intervals(spans)
        for start, end in merged:
            length = end - start
            role = _classify_wall_role(
                kind=kind,
                line_coord=line_coord,
                span_length=length,
                major_grid=major_grid,
            )
            walls.append(
                WallSegment(
                    id=f"w_{floor_id}_{orientation[0]}_{line_coord}_{start}_{end}",
                    floor_id=floor_id,
                    orientation=orientation,
                    line_coord_mm=line_coord,
                    span_start_mm=start,
                    span_end_mm=end,
                    role=role,
                    kind=kind,
                )
            )

    walls.sort(
        key=lambda wall: (
            0 if wall.orientation == "vertical" else 1,
            wall.line_coord_mm,
            wall.span_start_mm,
            wall.span_end_mm,
        )
    )
    return walls


def _classify_wall_role(kind: str, line_coord: int, span_length: int, major_grid: int) -> str:
    """Assign a structural role proxy to a merged wall segment.

    Args:
        kind: Segment class (`interior` or `exterior`).
        line_coord: Segment line coordinate in mm.
        span_length: Segment length in mm.
        major_grid: Major grid size in mm.

    Returns:
        One of `load_bearing`, `candidate_bearing`, or `partition`.
    """
    if kind == "exterior":
        return "load_bearing"
    if line_coord % major_grid == 0 and span_length >= major_grid:
        return "candidate_bearing"
    return "partition"


def _merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Merge overlapping or adjacent intervals.

    Args:
        intervals: List of `(start, end)` pairs.

    Returns:
        Sorted merged interval list.
    """
    if not intervals:
        return []
    sorted_intervals = sorted(intervals)
    merged: list[tuple[int, int]] = []
    cur_start, cur_end = sorted_intervals[0]
    for start, end in sorted_intervals[1:]:
        if start <= cur_end:
            cur_end = max(cur_end, end)
            continue
        merged.append((cur_start, cur_end))
        cur_start, cur_end = start, end
    merged.append((cur_start, cur_end))
    return merged


def _line_interval_map(
    walls: list[WallSegment],
    orientation: str,
) -> dict[int, list[tuple[int, int]]]:
    """Group wall intervals by line coordinate for one orientation.

    Args:
        walls: Wall segments across one floor.
        orientation: `vertical` or `horizontal`.

    Returns:
        Mapping from line coordinate to merged interval spans.
    """
    grouped: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for wall in walls:
        if wall.orientation != orientation:
            continue
        grouped[wall.line_coord_mm].append((wall.span_start_mm, wall.span_end_mm))
    return {line_coord: _merge_intervals(spans) for line_coord, spans in grouped.items()}


def _overlap_with_intervals(
    start: int,
    end: int,
    intervals: list[tuple[int, int]],
) -> int:
    """Compute overlap length between one span and a set of merged intervals.

    Args:
        start: Query span start.
        end: Query span end.
        intervals: Merged intervals to compare against.

    Returns:
        Total overlap length in mm.
    """
    overlap = 0
    for left, right in intervals:
        intersection = min(end, right) - max(start, left)
        if intersection > 0:
            overlap += intersection
    return overlap


def _quadrant_bearing_lengths(
    walls: list[WallSegment],
    width: int,
    depth: int,
) -> tuple[int, int, int, int]:
    """Accumulate bearing-wall length into four quadrants.

    Args:
        walls: Bearing-role wall segments on one floor.
        width: Envelope width in mm.
        depth: Envelope depth in mm.

    Returns:
        Quadrant lengths `(top_left, top_right, bottom_left, bottom_right)`.
    """
    mid_x = width // 2
    mid_y = depth // 2
    top_left = 0
    top_right = 0
    bottom_left = 0
    bottom_right = 0

    for wall in walls:
        if wall.orientation == "vertical":
            top = max(0, min(wall.span_end_mm, mid_y) - wall.span_start_mm)
            bottom = max(0, wall.span_end_mm - max(wall.span_start_mm, mid_y))
            if wall.line_coord_mm < mid_x:
                top_left += top
                bottom_left += bottom
            elif wall.line_coord_mm > mid_x:
                top_right += top
                bottom_right += bottom
            else:
                top_left += top // 2
                top_right += top - (top // 2)
                bottom_left += bottom // 2
                bottom_right += bottom - (bottom // 2)
        else:
            left = max(0, min(wall.span_end_mm, mid_x) - wall.span_start_mm)
            right = max(0, wall.span_end_mm - max(wall.span_start_mm, mid_x))
            if wall.line_coord_mm < mid_y:
                top_left += left
                top_right += right
            elif wall.line_coord_mm > mid_y:
                bottom_left += left
                bottom_right += right
            else:
                top_left += left // 2
                bottom_left += left - (left // 2)
                top_right += right // 2
                bottom_right += right - (right // 2)

    return top_left, top_right, bottom_left, bottom_right


def _balance_ratio(quadrants: tuple[int, int, int, int]) -> float | None:
    """Compute weak/strong ratio from quadrant wall lengths.

    Args:
        quadrants: Quadrant bearing wall lengths.

    Returns:
        `min/max` ratio when any wall exists; `None` when all quadrants are zero.
    """
    strongest = max(quadrants)
    if strongest <= 0:
        return None
    weakest = min(quadrants)
    return weakest / strongest
