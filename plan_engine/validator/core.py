from __future__ import annotations

from plan_engine.models import PlanSolution, PlanSpec, ValidationReport
from plan_engine.validator.connectivity import validate_connectivity
from plan_engine.validator.geometry import validate_entry_exterior, validate_geometry, validate_space_presence
from plan_engine.validator.livability import validate_livability
from plan_engine.validator.stair import validate_stair


def validate_solution(spec: PlanSpec, solution: PlanSolution) -> ValidationReport:
    report = ValidationReport()
    validate_space_presence(spec, solution, report)
    validate_geometry(spec, solution, report)
    validate_entry_exterior(spec, solution, report)
    validate_connectivity(solution, report)
    validate_stair(spec, solution, report)
    validate_livability(spec, solution, report)
    return report
