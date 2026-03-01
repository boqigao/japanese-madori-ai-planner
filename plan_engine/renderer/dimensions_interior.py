from __future__ import annotations

from typing import TYPE_CHECKING

from plan_engine.renderer.helpers import _ordered_spaces

if TYPE_CHECKING:
    import svgwrite

    from plan_engine.models import FloorSolution, Rect


def draw_room_dimension_guides(renderer, drawing: svgwrite.Drawing, floor: FloorSolution) -> None:
    """Draw interior dimension guides for both rectangular and multi-rect spaces.

    Args:
        renderer: Active ``SvgRenderer`` instance providing coordinate conversion.
        drawing: SVG drawing object for the current floor.
        floor: Solved floor geometry including all spaces.

    Returns:
        None. The function mutates ``drawing`` in place.
    """
    for space in _ordered_spaces(floor):
        if space.type in {"entry", "toilet", "wc"}:
            continue
        if len(space.rects) == 1:
            # Single-rect spaces already carry ``WxH`` text in labels.
            # Skip extra internal guides to avoid collisions.
            continue
        for rect in space.rects:
            _draw_rect_dimension_guide(renderer, drawing, rect, text_color="#8a8a8a", compact=True)


def _draw_rect_dimension_guide(
    renderer,
    drawing: svgwrite.Drawing,
    rect: Rect,
    text_color: str,
    compact: bool = False,
) -> None:
    """Draw width/height dimension guide lines inside one rectangle.

    Args:
        renderer: Active ``SvgRenderer`` instance.
        drawing: SVG drawing object to mutate.
        rect: Target rectangle in millimeters.
        text_color: Color used for guide text.
        compact: Whether to use compact offsets for small component rectangles.

    Returns:
        None. Guide graphics are appended to ``drawing``.
    """
    if rect.w < 910 or rect.h < 1365:
        return
    inset = 70 if compact else 90
    x1 = rect.x + inset
    x2 = rect.x2 - inset
    y1 = rect.y + inset
    y2 = rect.y2 - inset
    if x2 <= x1 or y2 <= y1:
        return

    if x2 - x1 >= 620:
        y = rect.y + inset
        drawing.add(
            drawing.line(
                start=(renderer._x(x1), renderer._y(y)),
                end=(renderer._x(x2), renderer._y(y)),
                stroke="#9a9a9a",
                stroke_width=0.8,
            )
        )
        drawing.add(
            drawing.line(
                start=(renderer._x(x1), renderer._y(y - 28)),
                end=(renderer._x(x1), renderer._y(y + 28)),
                stroke="#9a9a9a",
                stroke_width=0.8,
            )
        )
        drawing.add(
            drawing.line(
                start=(renderer._x(x2), renderer._y(y - 28)),
                end=(renderer._x(x2), renderer._y(y + 28)),
                stroke="#9a9a9a",
                stroke_width=0.8,
            )
        )
        drawing.add(
            drawing.text(
                f"{rect.w}mm",
                insert=(renderer._x(x1 + 56), renderer._y(y - 22)),
                fill=text_color,
                font_size=7.6 if compact else 8.0,
                text_anchor="start",
            )
        )

    if y2 - y1 >= 620:
        x = rect.x + inset
        drawing.add(
            drawing.line(
                start=(renderer._x(x), renderer._y(y1)),
                end=(renderer._x(x), renderer._y(y2)),
                stroke="#9a9a9a",
                stroke_width=0.8,
            )
        )
        drawing.add(
            drawing.line(
                start=(renderer._x(x - 28), renderer._y(y1)),
                end=(renderer._x(x + 28), renderer._y(y1)),
                stroke="#9a9a9a",
                stroke_width=0.8,
            )
        )
        drawing.add(
            drawing.line(
                start=(renderer._x(x - 28), renderer._y(y2)),
                end=(renderer._x(x + 28), renderer._y(y2)),
                stroke="#9a9a9a",
                stroke_width=0.8,
            )
        )
        drawing.add(
            drawing.text(
                f"{rect.h}mm",
                insert=(renderer._x(x + 34), renderer._y(y1 + 64)),
                fill=text_color,
                font_size=7.6 if compact else 8.0,
                text_anchor="start",
            )
        )
