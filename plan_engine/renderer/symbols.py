from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import svgwrite

    from plan_engine.models import Rect


def draw_door_symbol(
    drawing: svgwrite.Drawing,
    p1: tuple[int, int],
    p2: tuple[int, int],
    exterior: bool,
    boundary: Rect | None,
    reverse_swing: bool,
    draw_arc: bool,
    force_arc_small: bool,
    x_fn,
    y_fn,
    scale: float,
) -> tuple[tuple[int, int], tuple[int, int]]:
    """Draw one door symbol and return the final wall opening segment.

    Args:
        drawing: SVG drawing object to mutate.
        p1: First endpoint of the host wall segment in mm coordinates.
        p2: Second endpoint of the host wall segment in mm coordinates.
        exterior: Whether the door is on the building exterior boundary.
        boundary: Building boundary rectangle, used to choose outward swing side.
        reverse_swing: If ``True``, mirror swing direction.
        draw_arc: If ``True``, draw the door swing arc.
        force_arc_small: If ``True``, allow drawing arc even on short interior edges.
        x_fn: Coordinate conversion function (mm -> px for x).
        y_fn: Coordinate conversion function (mm -> px for y).
        scale: Current render scale (px per mm).

    Returns:
        Opening segment endpoints in mm coordinates.
    """
    wall_cut_width = 7 if exterior else 6
    if p1[0] == p2[0]:
        x = p1[0]
        y_low = min(p1[1], p2[1])
        y_high = max(p1[1], p2[1])
        seg_len = y_high - y_low
        opening = min(980, max(760, int(seg_len * 0.45)))
        center = (y_low + y_high) / 2
        y1 = center - opening / 2
        y2 = center + opening / 2
        opening_segment = ((round(x), round(y1)), (round(x), round(y2)))
        drawing.add(
            drawing.line(
                start=(x_fn(x), y_fn(y1)),
                end=(x_fn(x), y_fn(y2)),
                stroke="#ffffff",
                stroke_width=wall_cut_width,
            )
        )
        if not exterior and seg_len <= 1100 and not force_arc_small:
            return opening_segment
        swing_sign = -1 if reverse_swing else 1
        if exterior and boundary is not None and x == boundary.x2 and not reverse_swing:
            swing_sign = -1
        if draw_arc:
            hinge = (x, y1)
            leaf = (x + swing_sign * opening * 0.65, y1 + opening * 0.65)
            drawing.add(
                drawing.line(
                    start=(x_fn(hinge[0]), y_fn(hinge[1])),
                    end=(x_fn(leaf[0]), y_fn(leaf[1])),
                    stroke="#595959",
                    stroke_width=1.2,
                )
            )
            arc_radius_px = opening * 0.65 * scale
            drawing.add(
                drawing.path(
                    d=(
                        f"M {x_fn(x)},{y_fn(y1 + opening * 0.65)} "
                        f"A {arc_radius_px},{arc_radius_px} 0 0 1 {x_fn(leaf[0])},{y_fn(leaf[1])}"
                    ),
                    fill="none",
                    stroke="#7a7a7a",
                    stroke_width=1.0,
                )
            )
        return opening_segment

    y = p1[1]
    x_low = min(p1[0], p2[0])
    x_high = max(p1[0], p2[0])
    seg_len = x_high - x_low
    opening = min(980, max(760, int(seg_len * 0.45)))
    center = (x_low + x_high) / 2
    x1 = center - opening / 2
    x2 = center + opening / 2
    opening_segment = ((round(x1), round(y)), (round(x2), round(y)))
    drawing.add(
        drawing.line(
            start=(x_fn(x1), y_fn(y)),
            end=(x_fn(x2), y_fn(y)),
            stroke="#ffffff",
            stroke_width=wall_cut_width,
        )
    )
    if not exterior and seg_len <= 1100 and not force_arc_small:
        return opening_segment
    swing_sign = -1 if reverse_swing else 1
    if exterior and boundary is not None and y == boundary.y2 and not reverse_swing:
        swing_sign = -1
    if draw_arc:
        hinge = (x1, y)
        leaf = (x1 + opening * 0.65, y + swing_sign * opening * 0.65)
        drawing.add(
            drawing.line(
                start=(x_fn(hinge[0]), y_fn(hinge[1])),
                end=(x_fn(leaf[0]), y_fn(leaf[1])),
                stroke="#595959",
                stroke_width=1.2,
            )
        )
        arc_radius_px = opening * 0.65 * scale
        drawing.add(
            drawing.path(
                d=(
                    f"M {x_fn(x1 + opening * 0.65)},{y_fn(y)} "
                    f"A {arc_radius_px},{arc_radius_px} 0 0 1 {x_fn(leaf[0])},{y_fn(leaf[1])}"
                ),
                fill="none",
                stroke="#7a7a7a",
                stroke_width=1.0,
            )
        )
    return opening_segment


def draw_window_symbol(
    drawing: svgwrite.Drawing,
    p1: tuple[int, int],
    p2: tuple[int, int],
    offset_ratio: float,
    x_fn,
    y_fn,
) -> tuple[tuple[int, int], tuple[int, int]]:
    """Draw a double-line window symbol and return its opening segment.

    Args:
        drawing: SVG drawing object to mutate.
        p1: First endpoint of the host wall segment in mm coordinates.
        p2: Second endpoint of the host wall segment in mm coordinates.
        offset_ratio: Relative center position (0..1) for placing the opening along the wall.
        x_fn: Coordinate conversion function (mm -> px for x).
        y_fn: Coordinate conversion function (mm -> px for y).

    Returns:
        Opening segment endpoints in mm coordinates.
    """
    if p1[0] == p2[0]:
        x = p1[0]
        y_low = min(p1[1], p2[1])
        y_high = max(p1[1], p2[1])
        seg_len = y_high - y_low
        win_len = min(1600, max(910, int(seg_len * 0.34)))
        center = y_low + seg_len * offset_ratio
        y1 = max(y_low + 120, center - win_len / 2)
        y2 = min(y_high - 120, y1 + win_len)
        drawing.add(
            drawing.line(
                start=(x_fn(x - 22), y_fn(y1)),
                end=(x_fn(x - 22), y_fn(y2)),
                stroke="#66a7ff",
                stroke_width=2.2,
            )
        )
        drawing.add(
            drawing.line(
                start=(x_fn(x + 22), y_fn(y1)),
                end=(x_fn(x + 22), y_fn(y2)),
                stroke="#66a7ff",
                stroke_width=2.2,
            )
        )
        return ((round(x), round(y1)), (round(x), round(y2)))

    y = p1[1]
    x_low = min(p1[0], p2[0])
    x_high = max(p1[0], p2[0])
    seg_len = x_high - x_low
    win_len = min(1600, max(910, int(seg_len * 0.34)))
    center = x_low + seg_len * offset_ratio
    x1 = max(x_low + 120, center - win_len / 2)
    x2 = min(x_high - 120, x1 + win_len)
    drawing.add(
        drawing.line(
            start=(x_fn(x1), y_fn(y - 22)),
            end=(x_fn(x2), y_fn(y - 22)),
            stroke="#66a7ff",
            stroke_width=2.2,
        )
    )
    drawing.add(
        drawing.line(
            start=(x_fn(x1), y_fn(y + 22)),
            end=(x_fn(x2), y_fn(y + 22)),
            stroke="#66a7ff",
            stroke_width=2.2,
        )
    )
    return ((round(x1), round(y)), (round(x2), round(y)))
