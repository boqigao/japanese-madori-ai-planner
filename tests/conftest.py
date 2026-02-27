from __future__ import annotations

from pathlib import Path

import pytest

from plan_engine.dsl import load_plan_spec
from plan_engine.solver import PlanSolver
from plan_engine.validator import validate_solution


@pytest.fixture(scope="session")
def sample_spec_path() -> Path:
    path = Path(__file__).resolve().parents[1] / "resources" / "specs" / "sample_two_floor.yaml"
    if not path.exists():
        raise FileNotFoundError(f"test fixture spec is missing: {path}")
    return path


@pytest.fixture(scope="session")
def sample_spec(sample_spec_path: Path):
    return load_plan_spec(sample_spec_path)


@pytest.fixture(scope="session")
def solved_solution(sample_spec):
    last_error: Exception | None = None
    for timeout in (15.0, 20.0, 25.0, 30.0, 45.0):
        for _ in range(2):
            solver = PlanSolver(max_time_seconds=timeout, num_workers=8)
            try:
                return solver.solve(sample_spec)
            except RuntimeError as exc:
                last_error = exc
    if last_error is not None:
        raise last_error
    raise RuntimeError("solver did not produce a solution for integration fixture")


@pytest.fixture(scope="session")
def solved_report(sample_spec, solved_solution):
    return validate_solution(sample_spec, solved_solution)
