from __future__ import annotations

import argparse
import logging
from pathlib import Path

from plan_engine.dsl import load_plan_spec
from plan_engine.io import write_report, write_solution_json
from plan_engine.models import ValidationReport
from plan_engine.renderer import SvgRenderer
from plan_engine.solver import PlanSolver
from plan_engine.validator import validate_solution

LOGGER = logging.getLogger(__name__)
EXIT_PARSE_FAILED = 2
EXIT_SOLVE_FAILED = 3
EXIT_VALIDATION_FAILED = 4


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI-Driven Madori Plan Engine (MVP)")
    parser.add_argument("--spec", required=True, help="Path to DSL YAML specification file")
    parser.add_argument(
        "--outdir",
        default="output",
        help="Output directory for solution.json, floor SVGs and report.txt",
    )
    parser.add_argument(
        "--solver-timeout",
        type=float,
        default=20.0,
        help="Max CP-SAT solve time in seconds",
    )
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    try:
        spec = load_plan_spec(args.spec)
    except Exception as exc:
        report = ValidationReport(errors=[f"dsl_parse_failed: {exc}"])
        write_report(report, outdir / "report.txt")
        LOGGER.error("Failed to parse plan spec. See %s", outdir / "report.txt")
        return EXIT_PARSE_FAILED

    solver = PlanSolver(max_time_seconds=args.solver_timeout)
    try:
        solution = solver.solve(spec)
    except Exception as exc:
        report = ValidationReport(errors=[f"solve_failed: {exc}"])
        write_report(report, outdir / "report.txt")
        LOGGER.error("No feasible plan could be solved. See %s", outdir / "report.txt")
        return EXIT_SOLVE_FAILED

    report = validate_solution(spec, solution)
    write_solution_json(solution, outdir / "solution.json")
    write_report(report, outdir / "report.txt")

    if not report.is_valid:
        LOGGER.error("Plan rejected by validation. See %s", outdir / "report.txt")
        return EXIT_VALIDATION_FAILED

    SvgRenderer().render(solution, outdir)
    LOGGER.info("Plan generated successfully in %s", outdir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
