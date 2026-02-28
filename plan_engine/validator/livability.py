from __future__ import annotations

from plan_engine.constants import EDGE_NAMES, TATAMI_MM2
from plan_engine.models import EnvelopeSpec, PlanSolution, PlanSpec, Rect, ValidationReport
from plan_engine.stair_logic import ordered_floor_ids, stair_portal_for_floor


def validate_livability(spec: PlanSpec, solution: PlanSolution, report: ValidationReport) -> None:
    """Check dimensional quality, area ratios, circulation metrics, and stair specs."""
    north_edge, south_edge = _resolve_north_south_edges(spec.site.north)
    target_by_floor_space: dict[tuple[str, str], float] = {}
    for floor_id, floor_spec in spec.floors.items():
        for space_spec in floor_spec.spaces:
            if space_spec.area.target_tatami is not None:
                target_by_floor_space[(floor_id, space_spec.id)] = space_spec.area.target_tatami

    for floor_id, floor in solution.floors.items():
        major_total = 0
        major_south_hits = 0
        service_total = 0
        service_north_hits = 0
        for space_id, space in floor.spaces.items():
            bbox = _bounding_rect(space.rects)
            short_side = min(bbox.w, bbox.h)
            area_jo = _space_area_jo(space.rects)
            target = target_by_floor_space.get((floor_id, space_id))

            if space.type == "entry" and short_side < 1365:
                report.warnings.append(
                    f"{floor_id}:{space_id} entry short side {short_side}mm is narrow (recommend >=1365mm)"
                )
            if space.type in {"storage", "ldk", "master_bedroom", "bedroom", "hall", "entry"} and target is not None:
                overshoot_limit = 1.5 if space.type == "hall" else 1.3
                if area_jo > target * overshoot_limit:
                    report.warnings.append(
                        f"{floor_id}:{space_id} {space.type} area {area_jo:.1f}jo exceeds {overshoot_limit:.1f}x target ({target:.1f}jo)"
                    )
            if space.type in {"bedroom", "master_bedroom"} and short_side < 2730:
                report.warnings.append(
                    f"{floor_id}:{space_id} bedroom short side {short_side}mm is below 2730mm livability threshold"
                )

            if space.type in {"ldk", "bedroom", "master_bedroom"}:
                major_total += 1
                touches_south = _space_touches_envelope_edge(
                    rects=space.rects,
                    edge=south_edge,
                    envelope=solution.envelope,
                )
                if touches_south:
                    major_south_hits += 1
                else:
                    report.warnings.append(
                        f"{floor_id}:{space_id} misses south-facing preference (south edge={south_edge})"
                    )
                report.diagnostics.append(
                    f"{floor_id}:{space_id} orientation major_south edge={south_edge} status={'ok' if touches_south else 'miss'}"
                )

            if space.type in {"washroom", "bath", "toilet", "wc", "storage"}:
                service_total += 1
                touches_north = _space_touches_envelope_edge(
                    rects=space.rects,
                    edge=north_edge,
                    envelope=solution.envelope,
                )
                if touches_north:
                    service_north_hits += 1
                else:
                    report.warnings.append(
                        f"{floor_id}:{space_id} misses north-facing service preference (north edge={north_edge})"
                    )
                report.diagnostics.append(
                    f"{floor_id}:{space_id} orientation service_north edge={north_edge} status={'ok' if touches_north else 'miss'}"
                )

        bath_spaces = [(sid, s) for sid, s in floor.spaces.items() if s.type == "bath"]
        wash_spaces = [(sid, s) for sid, s in floor.spaces.items() if s.type == "washroom"]
        if bath_spaces and not wash_spaces:
            report.errors.append(f"{floor_id}: bath exists without washroom")
        for bath_id, bath in bath_spaces:
            touches_wash = any(_spaces_touch(bath.rects, wash.rects) for _, wash in wash_spaces)
            if not touches_wash:
                report.errors.append(f"{floor_id}:{bath_id} bath is not adjacent to any washroom")

        hall_ids = [sid for sid, s in floor.spaces.items() if s.type == "hall"]
        for hall_id in hall_ids:
            hall = floor.spaces[hall_id]
            hall_short = min(_bounding_rect(hall.rects).w, _bounding_rect(hall.rects).h)
            door_degree = 0
            for left_id, right_id in floor.topology:
                if hall_id in (left_id, right_id):
                    door_degree += 1
            if hall_short < 1365 and door_degree >= 3:
                report.warnings.append(
                    f"{floor_id}:{hall_id} hall width {hall_short}mm with {door_degree} doors may cause circulation conflicts"
                )

        bedrooms = [
            (space_id, _space_area_jo(space.rects))
            for space_id, space in floor.spaces.items()
            if space.type == "bedroom"
        ]
        masters = [
            (space_id, _space_area_jo(space.rects))
            for space_id, space in floor.spaces.items()
            if space.type == "master_bedroom"
        ]
        if bedrooms and masters:
            max_bed = max(area for _, area in bedrooms)
            min_master = min(area for _, area in masters)
            if max_bed > min_master:
                report.warnings.append(
                    f"{floor_id}: secondary bedroom area ({max_bed:.1f}jo) exceeds master bedroom ({min_master:.1f}jo)"
                )

        if floor.stair is not None:
            stair = floor.stair
            height_delta = abs(stair.floor_height - stair.riser_count * stair.riser_mm)
            if height_delta > 2:
                report.warnings.append(
                    f"{floor_id}:{stair.id} stair height mismatch {stair.floor_height}mm vs risers {stair.riser_count}x{stair.riser_mm}mm"
                )
            if stair.riser_mm < 140 or stair.riser_mm > 230:
                report.warnings.append(
                    f"{floor_id}:{stair.id} riser {stair.riser_mm}mm outside preferred range 140-230mm"
                )
            if stair.tread_mm < 210:
                report.warnings.append(f"{floor_id}:{stair.id} tread {stair.tread_mm}mm is below preferred 210mm")
            if stair.landing_size[0] < 910 or stair.landing_size[1] < 910:
                report.warnings.append(
                    f"{floor_id}:{stair.id} landing {stair.landing_size[0]}x{stair.landing_size[1]}mm is below 910mm"
                )
        report.diagnostics.append(
            f"{floor_id}: orientation_summary north={north_edge} south={south_edge} "
            f"major_south={major_south_hits}/{major_total} service_north={service_north_hits}/{service_total}"
        )

    if len(solution.floors) >= 2:
        ordered = ordered_floor_ids(solution.floors.keys())
        top_floor = solution.floors.get(ordered[-1])
        if top_floor is not None and top_floor.stair is not None:
            portal = stair_portal_for_floor(
                stair_type=top_floor.stair.type,
                floor_index=len(ordered) - 1,
                floor_count=len(ordered),
                component_count=len(top_floor.stair.components),
            )
            if len(top_floor.stair.components) >= 2:
                void_area = sum(
                    rect.area for idx, rect in enumerate(top_floor.stair.components) if idx != portal.component_index
                )
                if void_area <= 0:
                    report.warnings.append(f"{ordered[-1]}: stair void/opening is missing on top floor")


def _bounding_rect(rects: list[Rect]) -> Rect:
    """Compute the axis-aligned bounding box of a list of rectangles."""
    min_x = min(rect.x for rect in rects)
    min_y = min(rect.y for rect in rects)
    max_x = max(rect.x2 for rect in rects)
    max_y = max(rect.y2 for rect in rects)
    return Rect(x=min_x, y=min_y, w=max_x - min_x, h=max_y - min_y)


def _space_area_jo(rects: list[Rect]) -> float:
    """Convert total rectangle area from mm2 to tatami (jo) units."""
    area_mm2 = sum(rect.area for rect in rects)
    return area_mm2 / TATAMI_MM2


def _spaces_touch(rects_a: list[Rect], rects_b: list[Rect]) -> bool:
    """Return whether any rectangle pair from two spaces shares an edge.

    Args:
        rects_a: First space rectangle list.
        rects_b: Second space rectangle list.

    Returns:
        ``True`` when at least one rectangle in ``rects_a`` touches one in
        ``rects_b`` by a positive-length shared boundary.
    """
    return any(rect_a.shares_edge_with(rect_b) for rect_a in rects_a for rect_b in rects_b)


def _resolve_north_south_edges(north: str) -> tuple[str, str]:
    """Map north token to envelope north/south edges.

    Args:
        north: Cardinal north direction token.

    Returns:
        Tuple ``(north_edge, south_edge)`` using edge names.

    Raises:
        ValueError: If ``north`` is not one of the supported edge tokens.
    """
    normalized = north.strip().lower()
    if normalized not in EDGE_NAMES:
        raise ValueError(f"unsupported site.north '{north}'; expected one of {sorted(EDGE_NAMES)}")
    mapping = {
        "top": ("top", "bottom"),
        "right": ("right", "left"),
        "bottom": ("bottom", "top"),
        "left": ("left", "right"),
    }
    return mapping[normalized]


def _space_touches_envelope_edge(rects: list[Rect], edge: str, envelope: EnvelopeSpec) -> bool:
    """Return whether any space component touches the requested envelope edge.

    Args:
        rects: Room component rectangles in mm units.
        edge: Envelope edge token (``left/right/top/bottom``).
        envelope: Site envelope dimensions in mm units.

    Returns:
        ``True`` when at least one rectangle component lies on the edge.
    """
    if edge == "left":
        return any(rect.x == 0 for rect in rects)
    if edge == "right":
        return any(rect.x2 == envelope.width for rect in rects)
    if edge == "top":
        return any(rect.y == 0 for rect in rects)
    if edge == "bottom":
        return any(rect.y2 == envelope.depth for rect in rects)
    raise ValueError(f"unsupported envelope edge '{edge}'")
