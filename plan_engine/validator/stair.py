from __future__ import annotations

from typing import TYPE_CHECKING

from plan_engine.constants import EDGE_NAMES
from plan_engine.stair_logic import ordered_floor_ids, stair_portal_for_floor

if TYPE_CHECKING:
    from plan_engine.models import PlanSolution, PlanSpec, Rect, ValidationReport


def validate_stair(spec: PlanSpec, solution: PlanSolution, report: ValidationReport) -> None:
    """Validate stair alignment across floors, portal positioning, and hall connectivity."""
    stair_specs = [floor.core.stair for floor in spec.floors.values() if floor.core.stair is not None]
    if not stair_specs:
        report.warnings.append("no stair declared")
        return
    stair = stair_specs[0]
    ordered_floors = ordered_floor_ids(solution.floors.keys())
    floor_rank = {floor_id: idx for idx, floor_id in enumerate(ordered_floors)}

    stair_bboxes: list[Rect] = []
    stair_components: list[list[Rect]] = []
    for floor_id, floor in solution.floors.items():
        if floor.stair is None:
            continue
        stair_bboxes.append(floor.stair.bbox)
        stair_components.append(floor.stair.components)
        if floor.stair.id != stair.id:
            report.errors.append(f"{floor_id}: stair id mismatch, expected '{stair.id}'")

    if len(stair_bboxes) >= 2:
        first = stair_bboxes[0]
        for other in stair_bboxes[1:]:
            if other != first:
                report.errors.append("stair projection is not aligned across floors")
                break

    if len(stair_components) >= 2:
        first_components = [(r.x, r.y, r.w, r.h) for r in stair_components[0]]
        for components in stair_components[1:]:
            if [(r.x, r.y, r.w, r.h) for r in components] != first_components:
                report.errors.append("stair components are not aligned across floors")
                break

    for floor_id, hall_id in stair.connects.items():
        floor_solution = solution.floors.get(floor_id)
        if floor_solution is None:
            report.errors.append(f"stair connect floor '{floor_id}' missing in solution")
            continue
        if floor_solution.stair is None:
            report.errors.append(f"stair missing on floor '{floor_id}'")
            continue
        hall = floor_solution.spaces.get(hall_id)
        if hall is None:
            report.errors.append(f"stair hall '{hall_id}' missing on floor '{floor_id}'")
            continue
        portal = stair_portal_for_floor(
            stair_type=stair.type,
            floor_index=floor_rank.get(floor_id, 0),
            floor_count=len(ordered_floors),
            component_count=len(floor_solution.stair.components),
        )
        if (
            floor_solution.stair.portal_component is not None
            and floor_solution.stair.portal_component != portal.component_index
        ):
            report.errors.append(
                f"{floor_id}: stair portal component mismatch (expected {portal.component_index}, got {floor_solution.stair.portal_component})"
            )
        if floor_solution.stair.portal_edge is not None and floor_solution.stair.portal_edge != portal.edge:
            report.errors.append(
                f"{floor_id}: stair portal edge mismatch (expected {portal.edge}, got {floor_solution.stair.portal_edge})"
            )

        portal_component = floor_solution.stair.components[portal.component_index]
        _validate_portal_internal(
            floor_id=floor_id,
            component=portal_component,
            edge=portal.edge,
            width=spec.site.envelope.width,
            depth=spec.site.envelope.depth,
            report=report,
        )

        segments = _shared_segments_on_portal_edge(portal_component, hall.rects, portal.edge)
        unique_segments = {_segment_key(segment) for segment in segments}
        if len(unique_segments) != 1:
            report.errors.append(
                f"{floor_id}: stair must connect hall '{hall_id}' through exactly one portal edge ({portal.edge})"
            )
            continue
        if _segment_length(next(iter(unique_segments))) < spec.grid.minor:
            report.errors.append(f"{floor_id}: stair portal width is below one minor grid")


def _shared_segments_on_portal_edge(
    portal_component: Rect,
    hall_rects: list[Rect],
    edge: str,
) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    """Find shared edge segments between a portal component and hall rects on the portal edge."""
    if edge not in EDGE_NAMES:
        return []
    segments: list[tuple[tuple[int, int], tuple[int, int]]] = []
    for hall_rect in hall_rects:
        segment = portal_component.shared_edge_segment(hall_rect)
        if segment is not None and _segment_on_portal_edge(
            portal_component=portal_component,
            segment=segment,
            edge=edge,
        ):
            segments.append(segment)
    return segments


def _segment_key(segment: tuple[tuple[int, int], tuple[int, int]]) -> tuple[tuple[int, int], tuple[int, int]]:
    """Normalize a segment to canonical ordering for deduplication."""
    p1, p2 = segment
    if p1 <= p2:
        return p1, p2
    return p2, p1


def _segment_length(segment: tuple[tuple[int, int], tuple[int, int]]) -> int:
    """Compute the Manhattan length of an axis-aligned segment."""
    p1, p2 = segment
    return abs(p2[0] - p1[0]) + abs(p2[1] - p1[1])


def _segment_on_portal_edge(
    portal_component: Rect,
    segment: tuple[tuple[int, int], tuple[int, int]],
    edge: str,
) -> bool:
    """Check whether a segment lies on the specified edge of a portal component."""
    (x1, y1), (x2, y2) = segment
    if edge == "left" and x1 == x2 == portal_component.x:
        return True
    if edge == "right" and x1 == x2 == portal_component.x2:
        return True
    if edge == "top" and y1 == y2 == portal_component.y:
        return True
    return bool(edge == "bottom" and y1 == y2 == portal_component.y2)


def _validate_portal_internal(
    floor_id: str,
    component: Rect,
    edge: str,
    width: int,
    depth: int,
    report: ValidationReport,
) -> None:
    """Check that a stair portal edge is not on the site exterior boundary."""
    if edge == "left" and component.x <= 0:
        report.errors.append(f"{floor_id}: stair portal edge left is on exterior boundary")
    elif edge == "right" and component.x2 >= width:
        report.errors.append(f"{floor_id}: stair portal edge right is on exterior boundary")
    elif edge == "top" and component.y <= 0:
        report.errors.append(f"{floor_id}: stair portal edge top is on exterior boundary")
    elif edge == "bottom" and component.y2 >= depth:
        report.errors.append(f"{floor_id}: stair portal edge bottom is on exterior boundary")
