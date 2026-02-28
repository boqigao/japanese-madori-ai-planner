from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from plan_engine.constants import is_indoor_space_type

if TYPE_CHECKING:
    from plan_engine.models import PlanSolution, ValidationReport


def write_solution_json(solution: PlanSolution, target: str | Path) -> Path:
    """Serialize a PlanSolution to a JSON file and return the path."""
    path = Path(target)
    path.write_text(json.dumps(solution.to_dict(), indent=2), encoding="utf-8")
    return path


def write_report(report: ValidationReport, target: str | Path) -> Path:
    """Write a ValidationReport as plain text to a file and return the path."""
    path = Path(target)
    path.write_text(report.to_text(), encoding="utf-8")
    return path


def append_area_summary_diagnostics(report: ValidationReport, solution: PlanSolution) -> None:
    """Append indoor/outdoor area summary lines to report diagnostics.

    Args:
        report: Mutable validation report receiving additional diagnostics.
        solution: Solved plan containing per-floor geometries.

    Returns:
        None.
    """
    floor_ids = sorted(
        solution.floors.keys(),
        key=lambda value: (int("".join(ch for ch in value if ch.isdigit()) or "9999"), value),
    )
    total_indoor = 0
    total_outdoor = 0
    for floor_id in floor_ids:
        floor = solution.floors[floor_id]
        indoor_mm2 = 0
        outdoor_mm2 = 0
        for space in floor.spaces.values():
            area_mm2 = sum(rect.area for rect in space.rects)
            if is_indoor_space_type(space.type):
                indoor_mm2 += area_mm2
            else:
                outdoor_mm2 += area_mm2
        if floor.stair is not None:
            indoor_mm2 += sum(rect.area for rect in floor.stair.components)
        total_indoor += indoor_mm2
        total_outdoor += outdoor_mm2
        report.diagnostics.append(
            f"{floor_id}: area indoor={indoor_mm2 / 1_000_000:.2f}sqm outdoor={outdoor_mm2 / 1_000_000:.2f}sqm"
        )
    report.diagnostics.append(
        f"total_area: indoor={total_indoor / 1_000_000:.2f}sqm outdoor={total_outdoor / 1_000_000:.2f}sqm"
    )
