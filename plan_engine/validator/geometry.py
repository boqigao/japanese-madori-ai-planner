from __future__ import annotations

from typing import TYPE_CHECKING

from plan_engine.constants import MAJOR_ROOM_TYPES, is_indoor_space_type
from plan_engine.models import Rect
from plan_engine.stair_logic import ordered_floor_ids

if TYPE_CHECKING:
    from plan_engine.models import PlanSolution, PlanSpec, ValidationReport


def validate_space_presence(spec: PlanSpec, solution: PlanSolution, report: ValidationReport) -> None:
    """Check that all specified spaces exist with valid geometry."""
    for floor_id, floor_spec in spec.floors.items():
        floor_solution = solution.floors.get(floor_id)
        if floor_solution is None:
            report.errors.append(f"missing floor solution for '{floor_id}'")
            continue

        expected_ids = {space.id for space in floor_spec.spaces}
        actual_ids = set(floor_solution.spaces.keys())
        missing = expected_ids - actual_ids
        extra = actual_ids - expected_ids
        if missing:
            report.errors.append(f"{floor_id}: missing spaces {sorted(missing)}")
        if extra:
            report.errors.append(f"{floor_id}: unexpected spaces {sorted(extra)}")

        for space_id, space in floor_solution.spaces.items():
            if not space.rects:
                report.errors.append(f"{floor_id}:{space_id} has no geometry")
                continue
            for rect in space.rects:
                if rect.w <= 0 or rect.h <= 0:
                    report.errors.append(f"{floor_id}:{space_id} has non-positive dimensions")


def validate_geometry(spec: PlanSpec, solution: PlanSolution, report: ValidationReport) -> None:
    """Validate geometry invariants for solved floor layouts.

    Checks include grid alignment, envelope containment, non-overlap,
    100% indoor buildable coverage, and exterior-touch requirements for
    major rooms (bedroom/master_bedroom/ldk).
    """
    minor = spec.grid.minor
    width = spec.site.envelope.width
    depth = spec.site.envelope.depth

    for floor_id, floor in solution.floors.items():
        all_rects: list[tuple[str, Rect]] = []
        indoor_area = 0
        outdoor_area = 0
        buildable_mask = floor.buildable_mask or [Rect(0, 0, width, depth)]
        for space in floor.spaces.values():
            for rect in space.rects:
                all_rects.append((space.id, rect))
                if is_indoor_space_type(space.type):
                    indoor_area += rect.area
                    if not _is_inside_any(rect, buildable_mask):
                        report.errors.append(f"{floor_id}:{space.id} must be inside floor buildable mask")
                else:
                    outdoor_area += rect.area
            if space.type in MAJOR_ROOM_TYPES and not any(
                _touches_exterior(rect, width, depth) for rect in space.rects
            ):
                report.errors.append(
                    f"{floor_id}:{space.id} ({space.type}) must touch exterior boundary with positive edge length"
                )
        if floor.stair is not None:
            for index, component in enumerate(floor.stair.components):
                all_rects.append((f"{floor.stair.id}_component_{index}", component))
                indoor_area += component.area
                if not _is_inside_any(component, buildable_mask):
                    report.errors.append(f"{floor_id}:{floor.stair.id} must be inside floor buildable mask")

        for entity_id, rect in all_rects:
            for value_name, value in (("x", rect.x), ("y", rect.y), ("w", rect.w), ("h", rect.h)):
                if value % minor != 0:
                    report.errors.append(
                        f"{floor_id}:{entity_id} {value_name}={value} is not aligned to {minor}mm grid"
                    )
            if rect.x < 0 or rect.y < 0 or rect.x2 > width or rect.y2 > depth:
                report.errors.append(f"{floor_id}:{entity_id} is outside site envelope")

        for i, (left_id, left_rect) in enumerate(all_rects):
            for right_id, right_rect in all_rects[i + 1 :]:
                if left_rect.overlaps(right_rect):
                    report.errors.append(f"{floor_id}:{left_id} overlaps {right_id}")

        buildable_area = (
            floor.indoor_buildable_area_mm2
            if floor.indoor_buildable_area_mm2 is not None
            else sum(rect.area for rect in buildable_mask)
        )
        if indoor_area != buildable_area:
            report.errors.append(
                f"{floor_id}: indoor area coverage must be 100% of buildable mask "
                f"(indoor={indoor_area}, buildable={buildable_area})"
            )
        report.diagnostics.append(
            f"{floor_id}: area_breakdown indoor={indoor_area}mm2 outdoor={outdoor_area}mm2 "
            f"buildable={buildable_area}mm2"
        )


def validate_entry_exterior(spec: PlanSpec, solution: PlanSolution, report: ValidationReport) -> None:
    """Ensure entry spaces exist on ground floor and touch the exterior boundary."""
    width = spec.site.envelope.width
    depth = spec.site.envelope.depth
    ordered = ordered_floor_ids(spec.floors.keys())
    if ordered:
        ground_floor = ordered[0]
        floor_solution = solution.floors.get(ground_floor)
        if floor_solution is not None:
            ground_entries = [space for space in floor_solution.spaces.values() if space.type == "entry"]
            if not ground_entries:
                report.errors.append(f"{ground_floor}: missing entry space")

    for floor_id, floor in solution.floors.items():
        for space_id, space in floor.spaces.items():
            if space.type != "entry":
                continue
            if not any(_touches_exterior(rect, width, depth) for rect in space.rects):
                report.errors.append(f"{floor_id}:{space_id} entry must touch exterior boundary")


def _touches_exterior(rect: Rect, width: int, depth: int) -> bool:
    """Check whether a rectangle touches the site envelope boundary."""
    return rect.x == 0 or rect.y == 0 or rect.x2 == width or rect.y2 == depth


def _is_inside_any(rect: Rect, containers: list[Rect]) -> bool:
    """Return True when ``rect`` is fully contained in at least one container."""
    return any(
        rect.x >= container.x
        and rect.y >= container.y
        and rect.x2 <= container.x2
        and rect.y2 <= container.y2
        for container in containers
    )
