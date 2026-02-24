from __future__ import annotations

import svgwrite

from plan_engine.constants import TATAMI_MM2
from plan_engine.models import FloorSolution, PlanSolution, Rect
from plan_engine.renderer.helpers import (
    LEGEND_ORDER,
    SPACE_COLORS,
    _clamped_room_label_anchor,
    _display_space_name,
    _ordered_spaces,
    _space_dimensions,
)


def draw_space_labels(renderer, drawing: svgwrite.Drawing, floor: FloorSolution) -> None:
    for space in _ordered_spaces(floor):
        area_mm2 = sum(rect.area for rect in space.rects)
        area_sqm = area_mm2 / 1_000_000
        area_jo = area_mm2 / TATAMI_MM2
        dims = _space_dimensions(space.rects)
        title = _display_space_name(space.id, space.type)
        lines = [title, f"{dims[0]}x{dims[1]}mm", f"{area_sqm:.1f}sqm / {area_jo:.1f}jo"]
        anchor = _clamped_room_label_anchor(space.rects, lines, renderer.scale)
        for idx, line in enumerate(lines):
            drawing.add(
                drawing.text(
                    line,
                    insert=(renderer._x(anchor[0]), renderer._y(anchor[1] - 120 + idx * 90)),
                    fill="#1b1b1b",
                    font_size=10,
                    text_anchor="middle",
                )
            )


def draw_title_block(
    renderer,
    drawing: svgwrite.Drawing,
    floor_id: str,
    solution: PlanSolution,
) -> None:
    drawing.add(
        drawing.text(
            f"{floor_id} Plan  ({solution.envelope.width} x {solution.envelope.depth} mm)",
            insert=(renderer.margin_px, renderer.margin_px - 40),
            fill="#111111",
            font_size=14,
        )
    )
    drawing.add(
        drawing.text(
            f"Scale: 1px={1 / renderer.scale:.1f}mm",
            insert=(renderer.margin_px, renderer.margin_px - 22),
            fill="#444444",
            font_size=10,
        )
    )


def draw_legend(renderer, drawing: svgwrite.Drawing, floor: FloorSolution, site_rect: Rect) -> None:
    used_types = {space.type for space in floor.spaces.values()}
    legend_items = [space_type for space_type in LEGEND_ORDER if space_type in used_types]
    if not legend_items:
        return

    box_x = renderer._x(site_rect.x2) + 16
    box_y = renderer.margin_px - 70
    row_h = 18
    box_h = row_h * (len(legend_items) + 3)
    drawing.add(
        drawing.rect(
            insert=(box_x, box_y),
            size=(170, box_h),
            fill="#ffffff",
            stroke="#777777",
            stroke_width=1,
        )
    )
    drawing.add(drawing.text("Legend", insert=(box_x + 8, box_y + 14), fill="#111111", font_size=11))
    for idx, space_type in enumerate(legend_items):
        y = box_y + 24 + idx * row_h
        drawing.add(
            drawing.rect(
                insert=(box_x + 8, y),
                size=(12, 12),
                fill=SPACE_COLORS.get(space_type, "#eeeeee"),
                stroke="#333333",
                stroke_width=1,
            )
        )
        drawing.add(
            drawing.text(
                _display_space_name(space_type, space_type),
                insert=(box_x + 26, y + 10),
                fill="#222222",
                font_size=10,
            )
        )
    symbol_y = box_y + 24 + len(legend_items) * row_h + 4
    drawing.add(
        drawing.line(
            start=(box_x + 8, symbol_y + 8),
            end=(box_x + 35, symbol_y + 8),
            stroke="#6aa4ff",
            stroke_width=4,
        )
    )
    drawing.add(drawing.text("Window", insert=(box_x + 42, symbol_y + 11), fill="#222222", font_size=10))
    drawing.add(
        drawing.line(
            start=(box_x + 8, symbol_y + 24),
            end=(box_x + 35, symbol_y + 24),
            stroke="#666666",
            stroke_width=2.4,
        )
    )
    drawing.add(
        drawing.path(
            d=f"M {box_x + 8},{symbol_y + 24} A 10,10 0 0 1 {box_x + 18},{symbol_y + 14}",
            fill="none",
            stroke="#666666",
            stroke_width=1.2,
        )
    )
    drawing.add(drawing.text("Door", insert=(box_x + 42, symbol_y + 27), fill="#222222", font_size=10))


def draw_north_arrow(renderer, drawing: svgwrite.Drawing, north: str) -> None:
    center_x = renderer.margin_px - 45
    center_y = renderer.margin_px + 18
    vectors = {
        "top": (0, -1),
        "bottom": (0, 1),
        "left": (-1, 0),
        "right": (1, 0),
    }
    dx, dy = vectors.get(north, (0, -1))
    end_x = center_x + dx * 30
    end_y = center_y + dy * 30
    drawing.add(
        drawing.line(
            start=(center_x, center_y),
            end=(end_x, end_y),
            stroke="#111111",
            stroke_width=2,
        )
    )
    head = [
        (end_x, end_y),
        (end_x - 6 * (dx + dy), end_y - 6 * (dy - dx)),
        (end_x - 6 * (dx - dy), end_y - 6 * (dy + dx)),
    ]
    drawing.add(drawing.polygon(points=head, fill="#111111"))
    drawing.add(drawing.text("N", insert=(center_x - 5, center_y - 36), fill="#111111", font_size=12))
