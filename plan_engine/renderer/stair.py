from __future__ import annotations

import svgwrite

from plan_engine.models import FloorSolution, Rect
from plan_engine.renderer.helpers import (
    _bounding_rect,
    _portal_for_floor,
    _portal_hall_opening_segment,
    _stair_label_point,
)


def draw_stair(
    renderer,
    drawing: svgwrite.Drawing,
    floor: FloorSolution,
    floor_index: int,
    total_floors: int,
) -> None:
    """Draw the complete stair visualization including components, steps, void indicators, and labels."""
    if floor.stair is None:
        return
    stair = floor.stair
    is_top_floor = total_floors > 1 and floor_index == total_floors - 1
    portal = _portal_for_floor(
        floor=floor,
        floor_index=floor_index,
        total_floors=total_floors,
    )
    access_indices = [portal.component_index]
    for index, component in enumerate(stair.components):
        is_void = is_top_floor and index not in access_indices
        drawing.add(
            drawing.rect(
                insert=(renderer._x(component.x), renderer._y(component.y)),
                size=(component.w * renderer.scale, component.h * renderer.scale),
                fill="#f4f4f4" if is_void else "#ffffff",
                stroke="#202020",
                stroke_width=2.6,
                stroke_dasharray="4,3" if is_void else "8,4",
            )
        )
        if is_void:
            draw_void_hatch(renderer, drawing, component)

    visible_step_indices = set(range(len(stair.components)))
    if is_top_floor:
        visible_step_indices = set(access_indices)
        void_components = [
            stair.components[index]
            for index in range(len(stair.components))
            if index not in access_indices
        ]
        if void_components:
            void_bbox = _bounding_rect(void_components)
            drawing.add(
                drawing.text(
                    "Open To Below",
                    insert=(renderer._x(void_bbox.x + void_bbox.w / 2), renderer._y(void_bbox.y + void_bbox.h / 2)),
                    fill="#555555",
                    font_size=9,
                    text_anchor="middle",
                )
            )
            draw_void_guardrail(renderer, drawing, void_bbox)

    draw_stair_steps(
        renderer,
        drawing,
        stair.type,
        stair.tread_count,
        stair.components,
        visible_indices=visible_step_indices,
    )
    direction = "UP"
    if is_top_floor:
        direction = "DN"
    label_x, label_y = _stair_label_point(stair.components, portal.component_index)
    drawing.add(
        drawing.text(
            f"Stair ({direction})",
            insert=(renderer._x(label_x), renderer._y(label_y)),
            fill="#202020",
            font_size=11,
            text_anchor="middle",
        )
    )
    stair_area_sqm = sum(component.area for component in stair.components) / 1_000_000
    drawing.add(
        drawing.text(
            f"{stair_area_sqm:.1f}sqm  H{stair.floor_height}  R{stair.riser_count}@{stair.riser_mm}",
            insert=(renderer._x(label_x), renderer._y(label_y + 120)),
            fill="#3a3a3a",
            font_size=8.5,
            text_anchor="middle",
        )
    )
    drawing.add(
        drawing.text(
            f"T{stair.tread_count}@{stair.tread_mm}  Landing {stair.landing_size[0]}x{stair.landing_size[1]}",
            insert=(renderer._x(label_x), renderer._y(label_y + 205)),
            fill="#3a3a3a",
            font_size=8.0,
            text_anchor="middle",
        )
    )


def draw_stair_connection_opening(
    renderer,
    drawing: svgwrite.Drawing,
    floor: FloorSolution,
    floor_index: int,
    total_floors: int,
) -> None:
    """Draw a wall opening between the stair portal and the connected hall."""
    if floor.stair is None:
        return
    hall_id = floor.stair.connects.get(floor.id)
    if hall_id is None:
        return
    hall = floor.spaces.get(hall_id)
    if hall is None:
        return
    portal = _portal_for_floor(
        floor=floor,
        floor_index=floor_index,
        total_floors=total_floors,
    )
    portal_component = floor.stair.components[portal.component_index]
    segment = _portal_hall_opening_segment(portal_component, hall.rects, portal.edge)
    if segment is None:
        return
    drawing.add(
        drawing.line(
            start=(renderer._x(segment[0][0]), renderer._y(segment[0][1])),
            end=(renderer._x(segment[1][0]), renderer._y(segment[1][1])),
            stroke="#ffffff",
            stroke_width=7,
        )
    )
    drawing.add(
        drawing.line(
            start=(renderer._x(segment[0][0]), renderer._y(segment[0][1])),
            end=(renderer._x(segment[1][0]), renderer._y(segment[1][1])),
            stroke="#5e5e5e",
            stroke_width=1.0,
        )
    )


def draw_stair_steps(
    renderer,
    drawing: svgwrite.Drawing,
    stair_type: str,
    tread_count: int,
    components: list[Rect],
    visible_indices: set[int] | None = None,
) -> None:
    """Draw tread lines for straight or L-shaped stair flights."""
    if tread_count <= 0 or not components:
        return
    if visible_indices is None:
        visible_indices = set(range(len(components)))

    if stair_type == "straight":
        if 0 not in visible_indices:
            return
        flight = components[0]
        for index in range(1, tread_count + 1):
            y = flight.y + (flight.h * index) / (tread_count + 1)
            drawing.add(
                drawing.line(
                    start=(renderer._x(flight.x + 0.12 * flight.w), renderer._y(y)),
                    end=(renderer._x(flight.x + 0.88 * flight.w), renderer._y(y)),
                    stroke="#2a2a2a",
                    stroke_width=1.4,
                )
            )
        return

    if len(components) < 3:
        return
    flight1, _, flight2 = components[0], components[1], components[2]
    run1 = max(1, tread_count // 2)
    run2 = max(1, tread_count - run1)
    if 0 in visible_indices:
        for index in range(1, run1 + 1):
            x = flight1.x + (flight1.w * index) / (run1 + 1)
            drawing.add(
                drawing.line(
                    start=(renderer._x(x), renderer._y(flight1.y)),
                    end=(renderer._x(x), renderer._y(flight1.y + flight1.h)),
                    stroke="#2a2a2a",
                    stroke_width=1.4,
                )
            )
    if 2 in visible_indices:
        for index in range(1, run2 + 1):
            y = flight2.y + (flight2.h * index) / (run2 + 1)
            drawing.add(
                drawing.line(
                    start=(renderer._x(flight2.x), renderer._y(y)),
                    end=(renderer._x(flight2.x + flight2.w), renderer._y(y)),
                    stroke="#2a2a2a",
                    stroke_width=1.4,
                )
            )


def draw_void_hatch(renderer, drawing: svgwrite.Drawing, rect: Rect) -> None:
    """Draw horizontal hatch lines indicating a floor void area."""
    spacing = 160
    y = rect.y + 80
    while y < rect.y2:
        drawing.add(
            drawing.line(
                start=(renderer._x(rect.x + 45), renderer._y(y)),
                end=(renderer._x(rect.x2 - 45), renderer._y(y)),
                stroke="#b8b8b8",
                stroke_width=0.9,
            )
        )
        y += spacing


def draw_void_guardrail(renderer, drawing: svgwrite.Drawing, rect: Rect) -> None:
    """Draw a dashed guardrail rectangle with label around a void area."""
    drawing.add(
        drawing.rect(
            insert=(renderer._x(rect.x), renderer._y(rect.y)),
            size=(rect.w * renderer.scale, rect.h * renderer.scale),
            fill="none",
            stroke="#7e7e7e",
            stroke_width=2.0,
            stroke_dasharray="3,2",
        )
    )
    drawing.add(
        drawing.text(
            "Guardrail",
            insert=(renderer._x(rect.x + rect.w / 2), renderer._y(rect.y + 120)),
            fill="#666666",
            font_size=8.5,
            text_anchor="middle",
        )
    )
