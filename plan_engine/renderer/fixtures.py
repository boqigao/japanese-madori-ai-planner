from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import svgwrite

    from plan_engine.models import FloorSolution, Rect


def draw_fixtures(renderer, drawing: svgwrite.Drawing, floor: FloorSolution) -> None:
    """Draw lightweight furniture/fixture symbols for readability.

    Args:
        renderer: SvgRenderer instance providing coordinate helpers.
        drawing: Floor drawing to mutate.
        floor: Floor solution containing room geometries.

    Returns:
        None.
    """
    for space in floor.spaces.values():
        if not space.rects:
            continue
        rect = max(space.rects, key=lambda value: value.area)

        # Compact wet types have small fixed modules — draw before size check.
        if space.type == "washstand":
            _draw_washstand(renderer, drawing, rect)
            continue
        if space.type == "shower":
            _draw_shower(renderer, drawing, rect)
            continue

        if rect.w < 1365 or rect.h < 1365:
            continue

        if space.type in {"bedroom", "master_bedroom"}:
            bed_w = min(rect.w * 0.56, 1820)
            bed_h = min(rect.h * 0.34, 1365)
            bed_x = rect.x + (rect.w - bed_w) / 2
            bed_y = rect.y + rect.h * 0.18
            drawing.add(
                drawing.rect(
                    insert=(renderer._x(bed_x), renderer._y(bed_y)),
                    size=(bed_w * renderer.scale, bed_h * renderer.scale),
                    fill="none",
                    stroke="#7f7f7f",
                    stroke_width=1.1,
                )
            )
            drawing.add(
                drawing.line(
                    start=(renderer._x(bed_x), renderer._y(bed_y + bed_h * 0.35)),
                    end=(renderer._x(bed_x + bed_w), renderer._y(bed_y + bed_h * 0.35)),
                    stroke="#7f7f7f",
                    stroke_width=0.9,
                )
            )
            continue

        if space.type == "ldk":
            counter_w = min(rect.w * 0.32, 2280)
            counter_h = min(rect.h * 0.10, 700)
            counter_x = rect.x + rect.w * 0.54
            counter_y = rect.y + rect.h * 0.10
            drawing.add(
                drawing.rect(
                    insert=(renderer._x(counter_x), renderer._y(counter_y)),
                    size=(counter_w * renderer.scale, counter_h * renderer.scale),
                    fill="none",
                    stroke="#8a6b4a",
                    stroke_width=1.0,
                )
            )
            leg_w = min(counter_h * 0.9, 650)
            leg_h = min(rect.h * 0.22, 1365)
            leg_x = counter_x + counter_w - leg_w
            leg_y = counter_y
            drawing.add(
                drawing.rect(
                    insert=(renderer._x(leg_x), renderer._y(leg_y)),
                    size=(leg_w * renderer.scale, leg_h * renderer.scale),
                    fill="none",
                    stroke="#8a6b4a",
                    stroke_width=1.0,
                )
            )
            stove_cx = counter_x + counter_w * 0.35
            stove_cy = counter_y + counter_h * 0.5
            for dx in (-90, 90):
                drawing.add(
                    drawing.circle(
                        center=(renderer._x(stove_cx + dx), renderer._y(stove_cy)),
                        r=max(3, 70 * renderer.scale),
                        fill="none",
                        stroke="#8a6b4a",
                        stroke_width=0.9,
                    )
                )
            sink_x = leg_x + leg_w * 0.15
            sink_y = leg_y + leg_h * 0.42
            sink_w = leg_w * 0.68
            sink_h = min(300, leg_h * 0.24)
            drawing.add(
                drawing.rect(
                    insert=(renderer._x(sink_x), renderer._y(sink_y)),
                    size=(sink_w * renderer.scale, sink_h * renderer.scale),
                    fill="none",
                    stroke="#8a6b4a",
                    stroke_width=0.9,
                )
            )
            island_w = min(rect.w * 0.22, 1365)
            island_h = min(rect.h * 0.12, 820)
            island_x = rect.x + rect.w * 0.40
            island_y = rect.y + rect.h * 0.42
            drawing.add(
                drawing.rect(
                    insert=(renderer._x(island_x), renderer._y(island_y)),
                    size=(island_w * renderer.scale, island_h * renderer.scale),
                    fill="none",
                    stroke="#8a6b4a",
                    stroke_width=1.0,
                )
            )
            continue

        if space.type in {"toilet", "wc"}:
            cx = rect.x + rect.w * 0.5
            cy = rect.y + rect.h * 0.55
            tank_w = min(rect.w * 0.42, 380)
            tank_h = min(rect.h * 0.14, 180)
            drawing.add(
                drawing.rect(
                    insert=(renderer._x(cx - tank_w / 2), renderer._y(rect.y + rect.h * 0.16)),
                    size=(tank_w * renderer.scale, tank_h * renderer.scale),
                    fill="none",
                    stroke="#6f6f6f",
                    stroke_width=1.0,
                )
            )
            drawing.add(
                drawing.ellipse(
                    center=(renderer._x(cx), renderer._y(cy)),
                    r=(max(12, rect.w * renderer.scale * 0.13), max(8, rect.h * renderer.scale * 0.18)),
                    fill="none",
                    stroke="#6f6f6f",
                    stroke_width=1.0,
                )
            )
            draw_vent_marker(renderer, drawing, rect)
            continue

        if space.type == "washroom":
            sink_w = min(rect.w * 0.34, 760)
            sink_h = min(rect.h * 0.22, 455)
            sink_x = rect.x + rect.w * 0.18
            sink_y = rect.y + rect.h * 0.18
            for offset in (0.0, rect.w * 0.40):
                drawing.add(
                    drawing.rect(
                        insert=(renderer._x(sink_x + offset), renderer._y(sink_y)),
                        size=(sink_w * renderer.scale, sink_h * renderer.scale),
                        fill="none",
                        stroke="#6f6f6f",
                        stroke_width=1.0,
                    )
                )
            drawing.add(
                drawing.line(
                    start=(renderer._x(rect.x + rect.w * 0.14), renderer._y(sink_y - 120)),
                    end=(renderer._x(rect.x + rect.w * 0.86), renderer._y(sink_y - 120)),
                    stroke="#8f8f8f",
                    stroke_width=0.8,
                )
            )
            draw_vent_marker(renderer, drawing, rect)
            continue

        if space.type == "bath":
            tub_w = min(rect.w * 0.62, 1365)
            tub_h = min(rect.h * 0.55, 910)
            tub_x = rect.x + rect.w * 0.2
            tub_y = rect.y + rect.h * 0.22
            drawing.add(
                drawing.rect(
                    insert=(renderer._x(tub_x), renderer._y(tub_y)),
                    size=(tub_w * renderer.scale, tub_h * renderer.scale),
                    rx=6,
                    ry=6,
                    fill="none",
                    stroke="#6f6f6f",
                    stroke_width=1.0,
                )
            )
            draw_vent_marker(renderer, drawing, rect)
            continue

        if space.type in {"storage", "wic"}:
            x1 = rect.x + rect.w * 0.12
            x2 = rect.x2 - rect.w * 0.12
            y1 = rect.y + rect.h * 0.18
            y2 = rect.y2 - rect.h * 0.18
            drawing.add(
                drawing.line(
                    start=(renderer._x(x1), renderer._y(y1)),
                    end=(renderer._x(x2), renderer._y(y1)),
                    stroke="#9a9a9a",
                    stroke_width=0.9,
                )
            )
            drawing.add(
                drawing.line(
                    start=(renderer._x(x1), renderer._y(y2)),
                    end=(renderer._x(x2), renderer._y(y2)),
                    stroke="#9a9a9a",
                    stroke_width=0.9,
                )
            )
            if space.type == "wic":
                mid = rect.y + rect.h * 0.5
                drawing.add(
                    drawing.line(
                        start=(renderer._x(x1), renderer._y(mid)),
                        end=(renderer._x(x2), renderer._y(mid)),
                        stroke="#9a9a9a",
                        stroke_width=0.7,
                        stroke_dasharray="5,3",
                    )
                )


def draw_vent_marker(renderer, drawing: svgwrite.Drawing, rect: Rect) -> None:
    """Draw a simple mechanical ventilation marker in a wet room.

    Args:
        renderer: SvgRenderer instance providing coordinate helpers.
        drawing: Floor drawing to mutate.
        rect: Wet-room rectangle in mm coordinates.

    Returns:
        None.
    """
    cx = rect.x2 - min(220, rect.w * 0.2)
    cy = rect.y + min(220, rect.h * 0.2)
    radius = max(3, 70 * renderer.scale)
    drawing.add(
        drawing.circle(
            center=(renderer._x(cx), renderer._y(cy)),
            r=radius,
            fill="none",
            stroke="#7c7c7c",
            stroke_width=0.9,
        )
    )
    drawing.add(
        drawing.line(
            start=(renderer._x(cx - 90), renderer._y(cy)),
            end=(renderer._x(cx + 90), renderer._y(cy)),
            stroke="#7c7c7c",
            stroke_width=0.8,
        )
    )
    drawing.add(
        drawing.line(
            start=(renderer._x(cx), renderer._y(cy - 90)),
            end=(renderer._x(cx), renderer._y(cy + 90)),
            stroke="#7c7c7c",
            stroke_width=0.8,
        )
    )


def _draw_washstand(renderer, drawing: svgwrite.Drawing, rect: Rect) -> None:
    """Draw a single sink symbol centered in a washstand module."""
    sink_w = min(rect.w * 0.60, 500)
    sink_h = min(rect.h * 0.36, 340)
    sink_x = rect.x + (rect.w - sink_w) / 2
    sink_y = rect.y + rect.h * 0.22
    drawing.add(
        drawing.rect(
            insert=(renderer._x(sink_x), renderer._y(sink_y)),
            size=(sink_w * renderer.scale, sink_h * renderer.scale),
            fill="none",
            stroke="#6f6f6f",
            stroke_width=1.0,
        )
    )
    drawing.add(
        drawing.line(
            start=(renderer._x(rect.x + rect.w * 0.18), renderer._y(sink_y - 80)),
            end=(renderer._x(rect.x + rect.w * 0.82), renderer._y(sink_y - 80)),
            stroke="#8f8f8f",
            stroke_width=0.8,
        )
    )
    draw_vent_marker(renderer, drawing, rect)


def _draw_shower(renderer, drawing: svgwrite.Drawing, rect: Rect) -> None:
    """Draw a shower symbol (drain circle + spray lines) in a shower module."""
    cx = rect.x + rect.w * 0.5
    cy = rect.y + rect.h * 0.5
    drain_r = max(3, min(rect.w, rect.h) * renderer.scale * 0.08)
    drawing.add(
        drawing.circle(
            center=(renderer._x(cx), renderer._y(cy)),
            r=drain_r,
            fill="none",
            stroke="#6f6f6f",
            stroke_width=1.0,
        )
    )
    # Spray lines radiating from center.
    spray_len = min(rect.w, rect.h) * 0.22
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (0.7, 0.7), (-0.7, 0.7), (0.7, -0.7), (-0.7, -0.7)):
        drawing.add(
            drawing.line(
                start=(renderer._x(cx + dx * spray_len * 0.4), renderer._y(cy + dy * spray_len * 0.4)),
                end=(renderer._x(cx + dx * spray_len), renderer._y(cy + dy * spray_len)),
                stroke="#6f6f6f",
                stroke_width=0.7,
            )
        )
    draw_vent_marker(renderer, drawing, rect)
