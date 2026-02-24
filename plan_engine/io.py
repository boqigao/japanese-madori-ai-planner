from __future__ import annotations

import json
from pathlib import Path

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
