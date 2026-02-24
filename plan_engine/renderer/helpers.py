from __future__ import annotations

from plan_engine.constants import MINOR_GRID_MM
from plan_engine.models import FloorSolution, Rect, SpaceGeometry
from plan_engine.stair_logic import StairPortal, stair_portal_for_floor

SPACE_COLORS = {
    "entry": "#f8f0d9",
    "hall": "#efe9ff",
    "ldk": "#ffe2b8",
    "bedroom": "#d9f2ff",
    "master_bedroom": "#c5e8ff",
    "toilet": "#fbe7e6",
    "wc": "#fbe7e6",
    "washroom": "#e7fbfb",
    "bath": "#dcecff",
    "storage": "#f0f0f0",
}
WINDOW_SPACE_TYPES = {"ldk", "bedroom", "master_bedroom", "entry"}
LEGEND_ORDER = [
    "entry",
    "hall",
    "ldk",
    "master_bedroom",
    "bedroom",
    "toilet",
    "washroom",
    "bath",
    "storage",
]


def _ordered_spaces(floor: FloorSolution) -> list[SpaceGeometry]:
    return [floor.spaces[key] for key in sorted(floor.spaces.keys())]


def _floor_rects(floor: FloorSolution) -> list[Rect]:
    rects: list[Rect] = []
    for space in floor.spaces.values():
        rects.extend(space.rects)
    if floor.stair is not None:
        rects.extend(floor.stair.components)
    return rects


def _bounding_rect(rects: list[Rect]) -> Rect:
    min_x = min(rect.x for rect in rects)
    min_y = min(rect.y for rect in rects)
    max_x = max(rect.x2 for rect in rects)
    max_y = max(rect.y2 for rect in rects)
    return Rect(min_x, min_y, max_x - min_x, max_y - min_y)


def _entity_rects(floor: FloorSolution, entity_id: str) -> list[Rect]:
    if entity_id in floor.spaces:
        return floor.spaces[entity_id].rects
    if floor.stair is not None and floor.stair.id == entity_id:
        return floor.stair.components
    return []


def _space_boundary_segments(rects: list[Rect]) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    cell = MINOR_GRID_MM
    occupied: set[tuple[int, int]] = set()
    for rect in rects:
        for x in range(rect.x, rect.x2, cell):
            for y in range(rect.y, rect.y2, cell):
                occupied.add((x, y))

    horizontal: dict[int, list[tuple[int, int]]] = {}
    vertical: dict[int, list[tuple[int, int]]] = {}

    for x, y in occupied:
        if (x, y - cell) not in occupied:
            horizontal.setdefault(y, []).append((x, x + cell))
        if (x, y + cell) not in occupied:
            horizontal.setdefault(y + cell, []).append((x, x + cell))
        if (x - cell, y) not in occupied:
            vertical.setdefault(x, []).append((y, y + cell))
        if (x + cell, y) not in occupied:
            vertical.setdefault(x + cell, []).append((y, y + cell))

    segments: list[tuple[tuple[int, int], tuple[int, int]]] = []
    for y, spans in horizontal.items():
        for x1, x2 in _merge_spans(spans):
            segments.append(((x1, y), (x2, y)))
    for x, spans in vertical.items():
        for y1, y2 in _merge_spans(spans):
            segments.append(((x, y1), (x, y2)))
    return segments


def _merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not spans:
        return []
    spans = sorted(spans)
    merged: list[tuple[int, int]] = []
    cur_start, cur_end = spans[0]
    for start, end in spans[1:]:
        if start <= cur_end:
            cur_end = max(cur_end, end)
            continue
        merged.append((cur_start, cur_end))
        cur_start, cur_end = start, end
    merged.append((cur_start, cur_end))
    return merged


def _shared_segment(
    rects_a: list[Rect], rects_b: list[Rect]
) -> tuple[tuple[int, int], tuple[int, int]] | None:
    best_segment: tuple[tuple[int, int], tuple[int, int]] | None = None
    best_length = 0
    for rect_a in rects_a:
        for rect_b in rects_b:
            segment = rect_a.shared_edge_segment(rect_b)
            if segment is None:
                continue
            length = _segment_length(segment[0], segment[1])
            if length > best_length:
                best_length = length
                best_segment = segment
    return best_segment


def _room_label_anchor(rects: list[Rect]) -> tuple[float, float]:
    total_area = sum(rect.area for rect in rects)
    if total_area <= 0:
        return float(rects[0].x), float(rects[0].y)
    cx = sum((rect.x + rect.w / 2) * rect.area for rect in rects) / total_area
    cy = sum((rect.y + rect.h / 2) * rect.area for rect in rects) / total_area
    return cx, cy


def _space_dimensions(rects: list[Rect]) -> tuple[int, int]:
    if len(rects) == 1:
        return rects[0].w, rects[0].h
    bbox = _bounding_rect(rects)
    return bbox.w, bbox.h


def _display_space_name(space_id: str, space_type: str) -> str:
    pretty_type = space_type.replace("_", " ").title()
    if space_id.startswith("auto_fill_"):
        return "Storage"
    if space_id == space_type:
        return pretty_type
    if space_type == "storage" and space_id.startswith("pantry"):
        return _humanize_space_id(space_id)
    if space_type == "hall" and space_id.startswith("hall"):
        return _humanize_space_id(space_id)
    if space_type in {"bedroom", "master_bedroom"} and space_id.startswith("bed"):
        suffix = "".join(ch for ch in space_id if ch.isdigit())
        if space_type == "master_bedroom":
            return f"Master Bedroom {suffix}" if suffix else "Master Bedroom"
        return f"Bedroom {suffix}" if suffix else "Bedroom"
    return _humanize_space_id(space_id)


def _humanize_space_id(space_id: str) -> str:
    chars: list[str] = []
    for idx, char in enumerate(space_id.replace("_", " ")):
        if char.isdigit() and idx > 0 and chars and chars[-1] != " ":
            chars.append(" ")
        chars.append(char)
    return "".join(chars).strip().title()


def _clamped_room_label_anchor(
    rects: list[Rect],
    lines: list[str],
    scale: float,
    font_size_px: float = 10.0,
) -> tuple[float, float]:
    anchor_x, anchor_y = _room_label_anchor(rects)
    bbox = _bounding_rect(rects)
    longest = max((len(line) for line in lines), default=8)
    approx_char_px = font_size_px * 0.58
    half_label_px = (longest * approx_char_px) / 2
    half_label_mm = half_label_px / scale
    x_margin_mm = max(220.0, half_label_mm + 60.0)
    y_margin_mm = 260.0

    min_x = bbox.x + x_margin_mm
    max_x = bbox.x2 - x_margin_mm
    min_y = bbox.y + y_margin_mm
    max_y = bbox.y2 - y_margin_mm

    if min_x <= max_x:
        anchor_x = min(max(anchor_x, min_x), max_x)
    else:
        anchor_x = bbox.x + bbox.w / 2
    if min_y <= max_y:
        anchor_y = min(max(anchor_y, min_y), max_y)
    else:
        anchor_y = bbox.y + bbox.h / 2
    return anchor_x, anchor_y


def _sorted_floor_ids(ids: set[str] | list[str]) -> list[str]:
    def key(value: str) -> tuple[int, str]:
        digits = "".join(ch for ch in value if ch.isdigit())
        return (int(digits) if digits else 10_000, value)

    return sorted(ids, key=key)


def _exterior_segments(rect: Rect, boundary: Rect) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    segments: list[tuple[tuple[int, int], tuple[int, int]]] = []
    if rect.x == boundary.x:
        segments.append(((rect.x, rect.y), (rect.x, rect.y2)))
    if rect.x2 == boundary.x2:
        segments.append(((rect.x2, rect.y), (rect.x2, rect.y2)))
    if rect.y == boundary.y:
        segments.append(((rect.x, rect.y), (rect.x2, rect.y)))
    if rect.y2 == boundary.y2:
        segments.append(((rect.x, rect.y2), (rect.x2, rect.y2)))
    return segments


def _segment_length(p1: tuple[int, int], p2: tuple[int, int]) -> int:
    return abs(p2[0] - p1[0]) + abs(p2[1] - p1[1])


def _segment_key(
    segment: tuple[tuple[int, int], tuple[int, int]]
) -> tuple[tuple[int, int], tuple[int, int]]:
    p1, p2 = segment
    if p1 <= p2:
        return p1, p2
    return p2, p1


def _door_line_key(segment: tuple[tuple[int, int], tuple[int, int]]) -> tuple[str, int]:
    p1, p2 = segment
    if p1[0] == p2[0]:
        return ("v", p1[0])
    return ("h", p1[1])


def _portal_for_floor(floor: FloorSolution, floor_index: int, total_floors: int) -> StairPortal:
    if floor.stair is None:
        raise ValueError("cannot resolve stair portal without stair geometry")
    if floor.stair.portal_component is not None and floor.stair.portal_edge is not None:
        return StairPortal(component_index=floor.stair.portal_component, edge=floor.stair.portal_edge)
    return stair_portal_for_floor(
        stair_type=floor.stair.type,
        floor_index=floor_index,
        floor_count=total_floors,
        component_count=len(floor.stair.components),
    )


def _portal_hall_opening_segment(
    portal_component: Rect,
    hall_rects: list[Rect],
    edge: str,
) -> tuple[tuple[int, int], tuple[int, int]] | None:
    best_segment: tuple[tuple[int, int], tuple[int, int]] | None = None
    best_length = 0
    for hall_rect in hall_rects:
        segment = _edge_shared_segment(portal_component, hall_rect, edge)
        if segment is None:
            continue
        length = _segment_length(segment[0], segment[1])
        if length > best_length:
            best_length = length
            best_segment = segment
    return best_segment


def _edge_shared_segment(
    portal_component: Rect,
    other: Rect,
    edge: str,
) -> tuple[tuple[int, int], tuple[int, int]] | None:
    if edge == "left":
        if other.x2 != portal_component.x:
            return None
        y1 = max(portal_component.y, other.y)
        y2 = min(portal_component.y2, other.y2)
        return ((portal_component.x, y1), (portal_component.x, y2)) if y2 > y1 else None
    if edge == "right":
        if other.x != portal_component.x2:
            return None
        y1 = max(portal_component.y, other.y)
        y2 = min(portal_component.y2, other.y2)
        return ((portal_component.x2, y1), (portal_component.x2, y2)) if y2 > y1 else None
    if edge == "top":
        if other.y2 != portal_component.y:
            return None
        x1 = max(portal_component.x, other.x)
        x2 = min(portal_component.x2, other.x2)
        return ((x1, portal_component.y), (x2, portal_component.y)) if x2 > x1 else None
    if edge == "bottom":
        if other.y != portal_component.y2:
            return None
        x1 = max(portal_component.x, other.x)
        x2 = min(portal_component.x2, other.x2)
        return ((x1, portal_component.y2), (x2, portal_component.y2)) if x2 > x1 else None
    return None


def _stair_label_point(components: list[Rect], portal_component_index: int) -> tuple[float, float]:
    if 0 <= portal_component_index < len(components):
        portal = components[portal_component_index]
        return portal.x + portal.w / 2, portal.y + portal.h / 2
    if len(components) >= 2:
        landing = components[1]
        return landing.x + landing.w / 2, landing.y + landing.h / 2
    first = components[0]
    return first.x + first.w / 2, first.y + first.h / 2
