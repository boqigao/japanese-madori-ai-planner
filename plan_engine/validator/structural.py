from __future__ import annotations

from plan_engine.models import PlanSolution, PlanSpec, ValidationReport
from plan_engine.structural.walls import build_structure_report, extract_solution_walls


def validate_structural(spec: PlanSpec, solution: PlanSolution, report: ValidationReport) -> None:
    """Append structural diagnostics to the validation report.

    This phase is warn-only: structural findings are surfaced as warnings and
    detailed structural lines, but do not invalidate a solution by themselves.

    Args:
        spec: Parsed plan specification.
        solution: Solved plan geometry.
        report: Mutable validation report to update in place.

    Returns:
        None.
    """
    structure_report = solution.structure_report
    if structure_report is None:
        walls = extract_solution_walls(solution)
        structure_report = build_structure_report(
            solution=solution,
            walls_by_floor=walls,
            direct_below_target=0.5,
            wall_balance_target=0.5,
        )

    report.structural.append("bearing model: proxy roles (exterior=load_bearing, major-grid interior=candidate_bearing)")
    report.structural.append(
        "threshold profile: direct_below>=0.50, wall_balance>=0.50 (warn-only mode)"
    )
    for floor_id, metrics in sorted(structure_report.floor_metrics.items()):
        ratio = "n/a" if metrics.wall_balance_ratio is None else f"{metrics.wall_balance_ratio:.2f}"
        report.structural.append(
            f"{floor_id}: bearing={metrics.total_bearing_length_mm}mm (V/H={metrics.bearing_vertical_mm}/{metrics.bearing_horizontal_mm}), balance={ratio}"
        )

    for item in structure_report.continuity_metrics:
        ratio = "n/a" if item.direct_below_ratio is None else f"{item.direct_below_ratio:.2f}"
        report.structural.append(
            f"{item.upper_floor_id}->{item.lower_floor_id} {item.orientation}: supported={item.supported_length_mm}/{item.upper_bearing_length_mm}mm, direct_below={ratio}"
        )

    if structure_report.vertical_transfer_required:
        report.structural.append(
            f"vertical_transfer_required={len(structure_report.vertical_transfer_required)}"
        )
        for item in structure_report.vertical_transfer_required[:8]:
            report.structural.append(
                f"{item.upper_floor_id}:{item.segment_id} unsupported={item.unsupported_length_mm}mm at {item.orientation}@{item.line_coord_mm}"
            )
        if len(structure_report.vertical_transfer_required) > 8:
            hidden = len(structure_report.vertical_transfer_required) - 8
            report.structural.append(f"... {hidden} more transfer-required segments")

    for warning in structure_report.warnings:
        report.warnings.append(f"structural: {warning}")

