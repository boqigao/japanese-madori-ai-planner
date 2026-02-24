from __future__ import annotations

from plan_engine.constants import TATAMI_MM2
from plan_engine.models import PlanSolution, PlanSpec, Rect, ValidationReport
from plan_engine.stair_logic import ordered_floor_ids, stair_portal_for_floor


def validate_livability(spec: PlanSpec, solution: PlanSolution, report: ValidationReport) -> None:
    """Check dimensional quality, area ratios, circulation metrics, and stair specs."""
    target_by_floor_space: dict[tuple[str, str], float] = {}
    for floor_id, floor_spec in spec.floors.items():
        for space_spec in floor_spec.spaces:
            if space_spec.area.target_tatami is not None:
                target_by_floor_space[(floor_id, space_spec.id)] = space_spec.area.target_tatami

    for floor_id, floor in solution.floors.items():
        for space_id, space in floor.spaces.items():
            bbox = _bounding_rect(space.rects)
            short_side = min(bbox.w, bbox.h)
            area_jo = _space_area_jo(space.rects)
            target = target_by_floor_space.get((floor_id, space_id))

            if space.type == "entry" and short_side < 1365:
                report.warnings.append(
                    f"{floor_id}:{space_id} entry short side {short_side}mm is narrow (recommend >=1365mm)"
                )
            if (
                space.type in {"storage", "ldk", "master_bedroom", "bedroom", "hall", "entry"}
                and target is not None
            ):
                overshoot_limit = 1.5 if space.type == "hall" else 1.3
                if area_jo <= target * overshoot_limit:
                    continue
                report.warnings.append(
                    f"{floor_id}:{space_id} {space.type} area {area_jo:.1f}jo exceeds {overshoot_limit:.1f}x target ({target:.1f}jo)"
                )
            if space.type in {"bedroom", "master_bedroom"} and short_side < 2730:
                report.warnings.append(
                    f"{floor_id}:{space_id} bedroom short side {short_side}mm is below 2730mm livability threshold"
                )

        hall_ids = [sid for sid, s in floor.spaces.items() if s.type == "hall"]
        for hall_id in hall_ids:
            hall = floor.spaces[hall_id]
            hall_short = min(_bounding_rect(hall.rects).w, _bounding_rect(hall.rects).h)
            door_degree = 0
            for left_id, right_id in floor.topology:
                if left_id == hall_id or right_id == hall_id:
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
            if stair.riser_mm < 140 or stair.riser_mm > 230:
                report.warnings.append(
                    f"{floor_id}:{stair.id} riser {stair.riser_mm}mm outside preferred range 140-230mm"
                )
            if stair.tread_mm < 210:
                report.warnings.append(
                    f"{floor_id}:{stair.id} tread {stair.tread_mm}mm is below preferred 210mm"
                )
            if stair.landing_size[0] < 910 or stair.landing_size[1] < 910:
                report.warnings.append(
                    f"{floor_id}:{stair.id} landing {stair.landing_size[0]}x{stair.landing_size[1]}mm is below 910mm"
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
                    rect.area
                    for idx, rect in enumerate(top_floor.stair.components)
                    if idx != portal.component_index
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
