from __future__ import annotations

from typing import TYPE_CHECKING

from plan_engine.renderer.helpers import (
    WINDOW_SPACE_TYPES,
    _door_line_key,
    _entity_rects,
    _exterior_segments,
    _segment_key,
    _segment_length,
    _shared_segment,
    _should_draw_interior_door,
)

if TYPE_CHECKING:
    import svgwrite

    from plan_engine.models import FloorSolution, Rect


def draw_interior_doors(renderer, drawing: svgwrite.Drawing, floor: FloorSolution) -> None:
    """Draw interior door symbols at shared space boundaries.

    Args:
        renderer: SvgRenderer instance providing coordinate helpers and door symbol drawing.
        drawing: Floor drawing to mutate.
        floor: Floor solution containing topology and space geometry.

    Returns:
        None.
    """
    door_entries: list[tuple[int, tuple[tuple[int, int], tuple[int, int]], str, str]] = []
    door_pairs: set[frozenset[str]] = set()
    for index, (left_id, right_id) in enumerate(floor.topology):
        if floor.stair is not None and (floor.stair.id in (left_id, right_id)):
            continue
        left_rects = _entity_rects(floor, left_id)
        right_rects = _entity_rects(floor, right_id)
        if not left_rects or not right_rects:
            continue
        segment = _shared_segment(left_rects, right_rects)
        if segment is None:
            continue
        left_type = floor.spaces[left_id].type if left_id in floor.spaces else left_id
        right_type = floor.spaces[right_id].type if right_id in floor.spaces else right_id
        if not _should_draw_interior_door(left_type, right_type):
            continue
        door_entries.append((index, segment, left_type, right_type))
        door_pairs.add(frozenset((left_id, right_id)))

    wash_ids = [space_id for space_id, space in floor.spaces.items() if space.type == "washroom"]
    for bath_id, bath_space in floor.spaces.items():
        if bath_space.type != "bath":
            continue
        for wash_id in wash_ids:
            pair_key = frozenset((bath_id, wash_id))
            if pair_key in door_pairs:
                continue
            segment = _shared_segment(bath_space.rects, floor.spaces[wash_id].rects)
            if segment is None:
                continue
            door_entries.append((len(door_entries), segment, "bath", "washroom"))
            door_pairs.add(pair_key)
            break

    line_counts: dict[tuple[str, int], int] = {}
    for _, segment, _, _ in door_entries:
        key = _door_line_key(segment)
        line_counts[key] = line_counts.get(key, 0) + 1

    for index, segment, left_type, right_type in door_entries:
        key = _door_line_key(segment)
        crowded_line = line_counts.get(key, 0) >= 3
        force_arc_small = left_type in {"bedroom", "master_bedroom"} or right_type in {
            "bedroom",
            "master_bedroom",
        }
        renderer._draw_door_symbol(
            drawing,
            segment[0],
            segment[1],
            exterior=False,
            boundary=None,
            reverse_swing=(index % 2 == 1),
            draw_arc=not crowded_line,
            force_arc_small=force_arc_small,
        )


def draw_entry_door(
    renderer, drawing: svgwrite.Drawing, floor: FloorSolution, building_rect: Rect
) -> (
    tuple[
        tuple[tuple[int, int], tuple[int, int]],
        tuple[tuple[int, int], tuple[int, int]],
    ]
    | None
):
    """Draw the primary entry door and return wall/opening segments.

    Args:
        renderer: SvgRenderer instance providing coordinate helpers and door symbol drawing.
        drawing: Floor drawing to mutate.
        floor: Floor solution containing spaces/topology.
        building_rect: Building footprint boundary.

    Returns:
        ``(wall_segment, opening_segment)`` when an entry door is placed, else ``None``.
    """
    entry_spaces = [space for space in floor.spaces.values() if space.type == "entry"]
    if not entry_spaces:
        return None

    best_segment: tuple[tuple[int, int], tuple[int, int]] | None = None
    best_len = -1
    for entry in entry_spaces:
        for rect in entry.rects:
            for segment in _exterior_segments(rect, building_rect):
                seg_len = _segment_length(segment[0], segment[1])
                if seg_len > best_len:
                    best_len = seg_len
                    best_segment = segment
    if best_segment is None:
        return None
    opening_segment = renderer._draw_door_symbol(
        drawing,
        best_segment[0],
        best_segment[1],
        exterior=True,
        boundary=building_rect,
        reverse_swing=False,
        draw_arc=True,
        force_arc_small=True,
    )
    return best_segment, opening_segment


def draw_windows(
    renderer,
    drawing: svgwrite.Drawing,
    floor: FloorSolution,
    building_rect: Rect,
    blocked_segments: set[tuple[tuple[int, int], tuple[int, int]]],
) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    """Draw exterior window symbols and return their opening segments.

    Args:
        renderer: SvgRenderer instance providing coordinate helpers and window symbol drawing.
        drawing: Floor drawing to mutate.
        floor: Floor solution containing spaces.
        building_rect: Building footprint boundary.
        blocked_segments: Exterior segments reserved by doors and excluded from windows.

    Returns:
        List of window opening segments in mm coordinates.
    """
    min_window_segment = 1365
    opening_segments: list[tuple[tuple[int, int], tuple[int, int]]] = []
    for space in floor.spaces.values():
        if space.type not in WINDOW_SPACE_TYPES:
            continue
        candidate_segments: list[tuple[tuple[int, int], tuple[int, int]]] = []
        for rect in space.rects:
            candidate_segments.extend(_exterior_segments(rect, building_rect))
        if not candidate_segments:
            continue

        seen: set[tuple[tuple[int, int], tuple[int, int]]] = set()
        unique_segments: list[tuple[tuple[int, int], tuple[int, int]]] = []
        for segment in candidate_segments:
            key = _segment_key(segment)
            if key in seen:
                continue
            seen.add(key)
            unique_segments.append(segment)

        for segment in unique_segments:
            key = _segment_key(segment)
            if key in blocked_segments:
                continue
            length = _segment_length(segment[0], segment[1])
            if length < min_window_segment:
                continue
            if length >= 3600:
                opening_segments.append(
                    renderer._draw_window_symbol(drawing, segment[0], segment[1], offset_ratio=0.28)
                )
                opening_segments.append(
                    renderer._draw_window_symbol(drawing, segment[0], segment[1], offset_ratio=0.72)
                )
            else:
                opening_segments.append(renderer._draw_window_symbol(drawing, segment[0], segment[1], offset_ratio=0.5))
    return opening_segments
