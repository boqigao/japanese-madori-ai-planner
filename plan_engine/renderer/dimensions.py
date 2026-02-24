from __future__ import annotations

import svgwrite

from plan_engine.models import FloorSolution, Rect
from plan_engine.renderer.helpers import _ordered_spaces


def draw_room_dimension_guides(renderer, drawing: svgwrite.Drawing, floor: FloorSolution) -> None:
    """Draw interior width/height dimension guides for qualifying rooms."""
    for space in _ordered_spaces(floor):
        if space.type == "hall":
            continue
        if space.type in {"entry", "toilet", "wc"}:
            continue
        if len(space.rects) != 1:
            continue
        rect = space.rects[0]
        if rect.w < 1365 or rect.h < 1820:
            continue
        inset = 90
        x1 = rect.x + inset
        x2 = rect.x2 - inset
        y1 = rect.y + inset
        y2 = rect.y2 - inset

        if x2 - x1 >= 700:
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
                    start=(renderer._x(x1), renderer._y(y - 30)),
                    end=(renderer._x(x1), renderer._y(y + 30)),
                    stroke="#9a9a9a",
                    stroke_width=0.8,
                )
            )
            drawing.add(
                drawing.line(
                    start=(renderer._x(x2), renderer._y(y - 30)),
                    end=(renderer._x(x2), renderer._y(y + 30)),
                    stroke="#9a9a9a",
                    stroke_width=0.8,
                )
            )
            drawing.add(
                drawing.text(
                    f"{rect.w}mm",
                    insert=(renderer._x((x1 + x2) / 2), renderer._y(y - 24)),
                    fill="#7a7a7a",
                    font_size=8,
                    text_anchor="middle",
                )
            )

        if y2 - y1 >= 700:
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
                    start=(renderer._x(x - 30), renderer._y(y1)),
                    end=(renderer._x(x + 30), renderer._y(y1)),
                    stroke="#9a9a9a",
                    stroke_width=0.8,
                )
            )
            drawing.add(
                drawing.line(
                    start=(renderer._x(x - 30), renderer._y(y2)),
                    end=(renderer._x(x + 30), renderer._y(y2)),
                    stroke="#9a9a9a",
                    stroke_width=0.8,
                )
            )
            drawing.add(
                drawing.text(
                    f"{rect.h}mm",
                    insert=(renderer._x(x + 46), renderer._y((y1 + y2) / 2)),
                    fill="#7a7a7a",
                    font_size=8,
                )
            )


def draw_dimensions(renderer, drawing: svgwrite.Drawing, site_rect: Rect, building_rect: Rect) -> None:
    """Draw exterior site and building dimension lines."""
    draw_dimension_line(
        renderer,
        drawing,
        (site_rect.x, site_rect.y),
        (site_rect.x2, site_rect.y),
        offset_px=-26,
        label=f"{site_rect.w} mm",
    )
    draw_dimension_line(
        renderer,
        drawing,
        (site_rect.x, site_rect.y),
        (site_rect.x, site_rect.y2),
        offset_px=-26,
        label=f"{site_rect.h} mm",
        vertical=True,
    )
    if building_rect != site_rect:
        draw_dimension_line(
            renderer,
            drawing,
            (building_rect.x, building_rect.y2),
            (building_rect.x2, building_rect.y2),
            offset_px=24,
            label=f"Building: {building_rect.w} mm",
        )
        draw_dimension_line(
            renderer,
            drawing,
            (building_rect.x2, building_rect.y),
            (building_rect.x2, building_rect.y2),
            offset_px=24,
            label=f"{building_rect.h} mm",
            vertical=True,
        )


def draw_dimension_line(
    renderer,
    drawing: svgwrite.Drawing,
    p1: tuple[int, int],
    p2: tuple[int, int],
    offset_px: float,
    label: str,
    vertical: bool = False,
) -> None:
    """Draw a single dimension line with tick marks and a label."""
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
