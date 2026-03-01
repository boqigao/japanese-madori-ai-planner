from __future__ import annotations

import itertools
from typing import TYPE_CHECKING

from plan_engine.constants import MINOR_GRID_MM
from plan_engine.renderer.helpers import _floor_rects

if TYPE_CHECKING:
    import svgwrite

    from plan_engine.models import FloorSolution, Rect


def draw_dimensions(
    renderer,
    drawing: svgwrite.Drawing,
    site_rect: Rect,
    building_rect: Rect,
    floor: FloorSolution,
    opening_segments: list[tuple[tuple[int, int], tuple[int, int]]],
) -> None:
    """Draw a three-layer exterior dimension system on all four edges.

    Layer A: total edge dimension.
    Layer B: segmented chain from perimeter room partitions.
    Layer C: segmented chain from door/window opening positions.

    Args:
        renderer: Active ``SvgRenderer`` instance.
        drawing: SVG drawing object to mutate.
        site_rect: Site envelope rectangle (unused for partitioning, kept for API compatibility).
        building_rect: Building footprint rectangle.
        floor: Solved floor geometry used to derive perimeter partitions.
        opening_segments: Exterior opening segments (entry door + windows) in mm coordinates.

    Returns:
        None. The function mutates ``drawing`` in place.
    """
    _ = site_rect
    offsets_total = {"top": -72.0, "bottom": 72.0, "left": -72.0, "right": 72.0}
    offsets_segmented = {"top": -54.0, "bottom": 54.0, "left": -54.0, "right": 54.0}
    offsets_opening = {"top": -36.0, "bottom": 36.0, "left": -36.0, "right": 36.0}

    for side in ("top", "bottom", "left", "right"):
        axis_start, axis_end, fixed = _side_axis(building_rect, side)

        _draw_dimension_chain(
            renderer=renderer,
            drawing=drawing,
            side=side,
            fixed=fixed,
            breakpoints=[axis_start, axis_end],
            offset_px=offsets_total[side],
            color="#545454",
            font_size=8.8,
            with_unit=True,
        )

        perimeter_breakpoints = _collect_perimeter_breakpoints(floor, building_rect, side)
        _draw_dimension_chain(
            renderer=renderer,
            drawing=drawing,
            side=side,
            fixed=fixed,
            breakpoints=perimeter_breakpoints,
            offset_px=offsets_segmented[side],
            color="#666666",
            font_size=8.2,
            with_unit=False,
        )

        opening_breakpoints = _collect_opening_breakpoints(opening_segments, building_rect, side)
        if 2 < len(opening_breakpoints) <= 10:
            _draw_dimension_chain(
                renderer=renderer,
                drawing=drawing,
                side=side,
                fixed=fixed,
                breakpoints=opening_breakpoints,
                offset_px=offsets_opening[side],
                color="#7a7a7a",
                font_size=7.8,
                min_label_length=MINOR_GRID_MM * 2,
                with_unit=False,
            )


def _draw_dimension_chain(
    renderer,
    drawing: svgwrite.Drawing,
    side: str,
    fixed: int,
    breakpoints: list[int],
    offset_px: float,
    color: str,
    font_size: float,
    min_label_length: int = MINOR_GRID_MM,
    with_unit: bool = False,
) -> None:
    """Draw one continuous dimension chain with ticks and per-segment labels.

    Args:
        renderer: Active ``SvgRenderer`` instance.
        drawing: SVG drawing object to mutate.
        side: One of ``top``, ``bottom``, ``left``, ``right``.
        fixed: Constant coordinate of the side (y for top/bottom, x for left/right).
        breakpoints: Ordered axis coordinates marking chain split points.
        offset_px: Pixel offset from wall toward the outside.
        color: Stroke/text color.
        font_size: Label font size in px.
        min_label_length: Minimum segment length (mm) for showing a label.
        with_unit: Whether to append ``mm`` unit in the label text.

    Returns:
        None. The dimension chain is appended to ``drawing``.
    """
    points = sorted(set(breakpoints))
    if len(points) < 2:
        return

    if side in {"top", "bottom"}:
        wall_y = renderer._y(fixed)
        chain_y = wall_y + offset_px
        x_start = renderer._x(points[0])
        x_end = renderer._x(points[-1])
        drawing.add(
            drawing.line(
                start=(x_start, chain_y),
                end=(x_end, chain_y),
                stroke=color,
                stroke_width=1.0,
            )
        )
        for value in points:
            x = renderer._x(value)
            drawing.add(
                drawing.line(
                    start=(x, wall_y),
                    end=(x, chain_y),
                    stroke=color,
                    stroke_width=0.8,
                )
            )
            drawing.add(
                drawing.line(
                    start=(x, chain_y - 3),
                    end=(x, chain_y + 3),
                    stroke=color,
                    stroke_width=1.0,
                )
            )
        for left, right in itertools.pairwise(points):
            if right <= left:
                continue
            segment_len = right - left
            if segment_len < min_label_length:
                continue
            mid_x = renderer._x((left + right) / 2)
            label_y = chain_y - 3 if offset_px < 0 else chain_y + 10
            drawing.add(
                drawing.text(
                    f"{segment_len}mm" if with_unit else f"{segment_len}",
                    insert=(mid_x, label_y),
                    fill=color,
                    font_size=font_size,
                    text_anchor="middle",
                )
            )
        return

    wall_x = renderer._x(fixed)
    chain_x = wall_x + offset_px
    y_start = renderer._y(points[0])
    y_end = renderer._y(points[-1])
    drawing.add(
        drawing.line(
            start=(chain_x, y_start),
            end=(chain_x, y_end),
            stroke=color,
            stroke_width=1.0,
        )
    )
    for value in points:
        y = renderer._y(value)
        drawing.add(
            drawing.line(
                start=(wall_x, y),
                end=(chain_x, y),
                stroke=color,
                stroke_width=0.8,
            )
        )
        drawing.add(
            drawing.line(
                start=(chain_x - 3, y),
                end=(chain_x + 3, y),
                stroke=color,
                stroke_width=1.0,
            )
        )
    for top, bottom in itertools.pairwise(points):
        if bottom <= top:
            continue
        segment_len = bottom - top
        if segment_len < min_label_length:
            continue
        mid_y = renderer._y((top + bottom) / 2)
        label_x = chain_x - 4 if offset_px < 0 else chain_x + 5
        drawing.add(
            drawing.text(
                f"{segment_len}mm" if with_unit else f"{segment_len}",
                insert=(label_x, mid_y),
                fill=color,
                font_size=font_size,
            )
        )


def _collect_perimeter_breakpoints(floor: FloorSolution, building_rect: Rect, side: str) -> list[int]:
    """Collect edge breakpoints produced by space/stair perimeter segmentation.

    Args:
        floor: Floor geometry providing room and stair rectangles.
        building_rect: Building footprint boundary.
        side: Edge selector (``top``/``bottom``/``left``/``right``).

    Returns:
        Sorted list of unique breakpoint coordinates on the side axis.
    """
    axis_start, axis_end, _ = _side_axis(building_rect, side)
    intervals: list[tuple[int, int]] = []
    for rect in _floor_rects(floor):
        if (side == "top" and rect.y == building_rect.y) or (side == "bottom" and rect.y2 == building_rect.y2):
            intervals.append((rect.x, rect.x2))
        elif (side == "left" and rect.x == building_rect.x) or (side == "right" and rect.x2 == building_rect.x2):
            intervals.append((rect.y, rect.y2))

    points = {axis_start, axis_end}
    for start, end in intervals:
        clipped_start = max(axis_start, min(axis_end, start))
        clipped_end = max(axis_start, min(axis_end, end))
        if clipped_end > clipped_start:
            points.add(clipped_start)
            points.add(clipped_end)
    return _normalize_breakpoints(points, axis_start, axis_end)


def _collect_opening_breakpoints(
    opening_segments: list[tuple[tuple[int, int], tuple[int, int]]],
    building_rect: Rect,
    side: str,
) -> list[int]:
    """Collect edge breakpoints produced by exterior openings on one side.

    Args:
        opening_segments: Opening line segments in mm coordinates.
        building_rect: Building footprint boundary.
        side: Edge selector (``top``/``bottom``/``left``/``right``).

    Returns:
        Sorted list of unique breakpoints including side start/end and opening split points.
    """
    axis_start, axis_end, fixed = _side_axis(building_rect, side)
    points = {axis_start, axis_end}
    for p1, p2 in opening_segments:
        if not _segment_on_side(p1, p2, side, fixed):
            continue
        if side in {"top", "bottom"}:
            start = _snap_to_minor(min(p1[0], p2[0]))
            end = _snap_to_minor(max(p1[0], p2[0]))
        else:
            start = _snap_to_minor(min(p1[1], p2[1]))
            end = _snap_to_minor(max(p1[1], p2[1]))
        start = max(axis_start, min(axis_end, start))
        end = max(axis_start, min(axis_end, end))
        if end - start < MINOR_GRID_MM:
            continue
        points.add(start)
        points.add(end)
    return _normalize_breakpoints(points, axis_start, axis_end)


def _segment_on_side(
    p1: tuple[int, int],
    p2: tuple[int, int],
    side: str,
    fixed: int,
) -> bool:
    """Check whether a segment lies on a specific outer edge.

    Args:
        p1: First endpoint in mm coordinates.
        p2: Second endpoint in mm coordinates.
        side: Edge selector (``top``/``bottom``/``left``/``right``).
        fixed: Constant edge coordinate.

    Returns:
        ``True`` when the segment is collinear with the specified boundary edge.
    """
    if side in {"top", "bottom"}:
        return p1[1] == p2[1] == fixed
    return p1[0] == p2[0] == fixed


def _side_axis(building_rect: Rect, side: str) -> tuple[int, int, int]:
    """Resolve axis start/end and fixed coordinate for one building side.

    Args:
        building_rect: Building footprint boundary.
        side: Edge selector (``top``/``bottom``/``left``/``right``).

    Returns:
        Tuple ``(axis_start, axis_end, fixed)`` where:
        - for top/bottom: axis is x, fixed is y
        - for left/right: axis is y, fixed is x
    """
    if side == "top":
        return building_rect.x, building_rect.x2, building_rect.y
    if side == "bottom":
        return building_rect.x, building_rect.x2, building_rect.y2
    if side == "left":
        return building_rect.y, building_rect.y2, building_rect.x
    if side == "right":
        return building_rect.y, building_rect.y2, building_rect.x2
    raise ValueError(f"unsupported side '{side}'")


def _snap_to_minor(value: int) -> int:
    """Snap a coordinate to the nearest minor-grid multiple.

    Args:
        value: Coordinate value in mm.

    Returns:
        Coordinate snapped to nearest ``MINOR_GRID_MM``.
    """
    return int(round(value / MINOR_GRID_MM) * MINOR_GRID_MM)


def _normalize_breakpoints(points: set[int], axis_start: int, axis_end: int) -> list[int]:
    """Normalize breakpoint set to sorted, clamped, grid-aligned values.

    Args:
        points: Raw breakpoint coordinates.
        axis_start: Minimum axis bound.
        axis_end: Maximum axis bound.

    Returns:
        Sorted unique breakpoints within bounds and aligned to minor grid.
    """
    normalized: set[int] = {axis_start, axis_end}
    for value in points:
        snapped = _snap_to_minor(value)
        clamped = max(axis_start, min(axis_end, snapped))
        normalized.add(clamped)
    return sorted(normalized)


def draw_dimension_line(
    renderer,
    drawing: svgwrite.Drawing,
    p1: tuple[int, int],
    p2: tuple[int, int],
    offset_px: float,
    label: str,
    vertical: bool = False,
) -> None:
    """Draw a single legacy dimension line with endpoint ticks.

    Args:
        renderer: Active ``SvgRenderer`` instance.
        drawing: SVG drawing object to mutate.
        p1: First endpoint in mm coordinates.
        p2: Second endpoint in mm coordinates.
        offset_px: Pixel offset from the referenced segment.
        label: Dimension label text.
        vertical: Whether to draw a vertical dimension line.

    Returns:
        None. The function mutates ``drawing`` in place.
    """
    if vertical:
        x = renderer._x(p1[0]) + offset_px
        y1 = renderer._y(min(p1[1], p2[1]))
        y2 = renderer._y(max(p1[1], p2[1]))
        drawing.add(drawing.line(start=(x, y1), end=(x, y2), stroke="#666666", stroke_width=1.2))
        drawing.add(drawing.line(start=(x - 4, y1), end=(x + 4, y1), stroke="#666666", stroke_width=1.2))
        drawing.add(drawing.line(start=(x - 4, y2), end=(x + 4, y2), stroke="#666666", stroke_width=1.2))
        drawing.add(drawing.text(label, insert=(x + 6, (y1 + y2) / 2), fill="#666666", font_size=9))
        return

    y = renderer._y(p1[1]) + offset_px
    x1 = renderer._x(min(p1[0], p2[0]))
    x2 = renderer._x(max(p1[0], p2[0]))
    drawing.add(drawing.line(start=(x1, y), end=(x2, y), stroke="#666666", stroke_width=1.2))
    drawing.add(drawing.line(start=(x1, y - 4), end=(x1, y + 4), stroke="#666666", stroke_width=1.2))
    drawing.add(drawing.line(start=(x2, y - 4), end=(x2, y + 4), stroke="#666666", stroke_width=1.2))
    drawing.add(drawing.text(label, insert=((x1 + x2) / 2 - 24, y - 4), fill="#666666", font_size=9))
