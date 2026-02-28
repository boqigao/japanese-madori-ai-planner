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


def test_preflight_reports_major_room_exterior_touch_impossible() -> None:
    spec = load_plan_spec(_fixture_path("major_room_exterior_impossible.yaml"))

    result = run_preflight(spec)

    assert any(
        "major-room exterior-touch is impossible because buildable mask has no exterior contact" in error
        for error in result.report.errors
    )
    assert any("buildable_mask so at least one rectangle reaches envelope edge" in item for item in result.report.suggestions)


def test_preflight_accepts_major_room_exterior_touch_feasible_floor() -> None:
    spec = load_plan_spec(_fixture_path("major_room_exterior_valid.yaml"))

    result = run_preflight(spec)

    assert not any("major-room exterior-touch is impossible" in error for error in result.report.errors)
