from __future__ import annotations

from pathlib import Path

from plan_engine.dsl import load_plan_spec
from plan_engine.preflight import run_preflight


def _fixture_path(name: str) -> Path:
    return Path(__file__).resolve().parents[2] / "resources" / "specs" / name


def test_preflight_accepts_valid_buildable_balcony_topology() -> None:
    spec = load_plan_spec(_fixture_path("buildable_balcony_valid.yaml"))

    result = run_preflight(spec)

    assert not result.report.errors


def test_preflight_reports_overlapping_buildable_mask() -> None:
    spec = load_plan_spec(_fixture_path("buildable_overlap_invalid.yaml"))

    result = run_preflight(spec)

    assert any("buildable mask rectangles must not overlap" in error for error in result.report.errors)


def test_preflight_reports_outdoor_missing_indoor_access_edge() -> None:
    spec = load_plan_spec(_fixture_path("buildable_balcony_missing_access.yaml"))

    result = run_preflight(spec)

    assert any("outdoor space has no indoor access topology edge" in error for error in result.report.errors)
