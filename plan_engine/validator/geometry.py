from __future__ import annotations

from plan_engine.models import PlanSolution, PlanSpec, Rect, ValidationReport
from plan_engine.stair_logic import ordered_floor_ids


def validate_space_presence(spec: PlanSpec, solution: PlanSolution, report: ValidationReport) -> None:
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
    minor = spec.grid.minor
    width = spec.site.envelope.width
    depth = spec.site.envelope.depth

    for floor_id, floor in solution.floors.items():
        all_rects: list[tuple[str, Rect]] = []
        for space in floor.spaces.values():
            for rect in space.rects:
                all_rects.append((space.id, rect))
        if floor.stair is not None:
            for index, component in enumerate(floor.stair.components):
                all_rects.append((f"{floor.stair.id}_component_{index}", component))

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

        covered_area = sum(rect.area for _, rect in all_rects)
        envelope_area = width * depth
        if covered_area != envelope_area:
            report.errors.append(
                f"{floor_id}: area coverage must be 100% (covered={covered_area}, envelope={envelope_area})"
            )


def validate_entry_exterior(spec: PlanSpec, solution: PlanSolution, report: ValidationReport) -> None:
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
    return rect.x == 0 or rect.y == 0 or rect.x2 == width or rect.y2 == depth
