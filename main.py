from __future__ import annotations

import argparse
from pathlib import Path

from plan_engine.dsl import load_plan_spec
from plan_engine.io import write_report, write_solution_json
from plan_engine.models import ValidationReport
from plan_engine.renderer import SvgRenderer
from plan_engine.solver import PlanSolver
from plan_engine.validator import validate_solution


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
    args = parse_args()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    try:
        spec = load_plan_spec(args.spec)
    except Exception as exc:
        report = ValidationReport(errors=[f"dsl_parse_failed: {exc}"])
        write_report(report, outdir / "report.txt")
        print(f"Failed to parse plan spec. See {outdir / 'report.txt'}")
        return 2

    solver = PlanSolver(max_time_seconds=args.solver_timeout)
    try:
        solution = solver.solve(spec)
    except Exception as exc:
        report = ValidationReport(errors=[f"solve_failed: {exc}"])
        write_report(report, outdir / "report.txt")
        print(f"No feasible plan could be solved. See {outdir / 'report.txt'}")
        return 2

    report = validate_solution(spec, solution)
    write_solution_json(solution, outdir / "solution.json")
    write_report(report, outdir / "report.txt")

    if not report.is_valid:
        print(f"Plan rejected by validation. See {outdir / 'report.txt'}")
        return 2

    SvgRenderer().render(solution, outdir)
    print(f"Plan generated successfully in {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
