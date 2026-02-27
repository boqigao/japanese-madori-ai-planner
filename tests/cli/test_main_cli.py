from __future__ import annotations

import argparse
from pathlib import Path

import main as cli
from plan_engine.models import ValidationReport


class _FakeSolver:
    def __init__(self, *, result=None, exc: Exception | None = None) -> None:
        self._result = result
        self._exc = exc
        self.last_timeout_seconds: float | None = None

    def solve(self, _spec):
        if self._exc is not None:
            raise self._exc
        return self._result


class _FakeRenderer:
    def __init__(self) -> None:
        self.called = False

    def render(self, _solution, outdir):
        self.called = True
        target = Path(outdir)
        target.mkdir(parents=True, exist_ok=True)
        (target / "dummy.svg").write_text("svg", encoding="utf-8")
        return [target / "dummy.svg"]


def test_main_parse_failure(monkeypatch, tmp_path: Path) -> None:
    args = argparse.Namespace(spec="x.yaml", outdir=str(tmp_path), solver_timeout=1.0)
    monkeypatch.setattr(cli, "parse_args", lambda: args)

    def _raise(_path):
        raise ValueError("bad yaml")

    monkeypatch.setattr(cli, "load_plan_spec", _raise)

    code = cli.main()
    assert code == cli.EXIT_PARSE_FAILED
    assert "dsl_parse_failed" in (tmp_path / "report.txt").read_text(encoding="utf-8")


def test_main_solve_failure(monkeypatch, tmp_path: Path, sample_spec) -> None:
    args = argparse.Namespace(spec="x.yaml", outdir=str(tmp_path), solver_timeout=1.0)
    monkeypatch.setattr(cli, "parse_args", lambda: args)
    monkeypatch.setattr(cli, "load_plan_spec", lambda _path: sample_spec)
    monkeypatch.setattr(cli, "PlanSolver", lambda **_kwargs: _FakeSolver(exc=RuntimeError("infeasible")))

    code = cli.main()
    assert code == cli.EXIT_SOLVE_FAILED
    assert "solve_failed" in (tmp_path / "report.txt").read_text(encoding="utf-8")


def test_main_validation_failure(monkeypatch, tmp_path: Path, sample_spec, solved_solution) -> None:
    args = argparse.Namespace(spec="x.yaml", outdir=str(tmp_path), solver_timeout=1.0)
    monkeypatch.setattr(cli, "parse_args", lambda: args)
    monkeypatch.setattr(cli, "load_plan_spec", lambda _path: sample_spec)
    monkeypatch.setattr(cli, "PlanSolver", lambda **_kwargs: _FakeSolver(result=solved_solution))
    monkeypatch.setattr(cli, "validate_solution", lambda _spec, _solution: ValidationReport(errors=["bad"]))
    monkeypatch.setattr(cli, "SvgRenderer", _FakeRenderer)

    code = cli.main()
    assert code == cli.EXIT_VALIDATION_FAILED
    assert "errors=1" in (tmp_path / "report.txt").read_text(encoding="utf-8")


def test_main_success(monkeypatch, tmp_path: Path, sample_spec, solved_solution) -> None:
    args = argparse.Namespace(spec="x.yaml", outdir=str(tmp_path), solver_timeout=1.0)
    monkeypatch.setattr(cli, "parse_args", lambda: args)
    monkeypatch.setattr(cli, "load_plan_spec", lambda _path: sample_spec)
    monkeypatch.setattr(cli, "PlanSolver", lambda **_kwargs: _FakeSolver(result=solved_solution))
    monkeypatch.setattr(cli, "validate_solution", lambda _spec, _solution: ValidationReport())
    monkeypatch.setattr(cli, "SvgRenderer", _FakeRenderer)

    code = cli.main()
    assert code == 0
    assert (tmp_path / "solution.json").exists()
    assert (tmp_path / "report.txt").exists()
