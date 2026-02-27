from __future__ import annotations

from pathlib import Path

from plan_engine.dsl import load_plan_spec
from plan_engine.preflight import run_preflight


def _fixture_path(name: str) -> Path:
    return Path(__file__).resolve().parents[2] / "resources" / "specs" / name


def test_preflight_reports_bedroom_transit_violation() -> None:
    spec = load_plan_spec(_fixture_path("preflight_bedroom_transit_invalid.yaml"))

    result = run_preflight(spec)

    assert len(result.bedroom_violations) == 1
    violation = result.bedroom_violations[0]
    assert violation.floor_id == "F1"
    assert violation.bedroom_id == "bed2"
    assert violation.transit_bedroom_ids == ("bed1",)
    assert violation.path == ("entry", "hall1", "bed1", "bed2")

    assert (
        "preflight: F1:bed2 is only reachable through bedroom transit "
        "(path: entry -> hall1 -> bed1 -> bed2)"
    ) in result.report.errors
    assert "F1: blocked bedroom=bed2, transit_bedrooms=bed1" in result.report.diagnostics


def test_preflight_accepts_multi_floor_bedrooms_with_non_bedroom_path() -> None:
    spec = load_plan_spec(_fixture_path("preflight_bedroom_transit_valid_two_floor.yaml"))

    result = run_preflight(spec)

    assert result.bedroom_violations == ()
    assert not any("only reachable through bedroom transit" in err for err in result.report.errors)


def test_preflight_does_not_flag_when_direct_hall_path_exists() -> None:
    spec = load_plan_spec(_fixture_path("preflight_bedroom_transit_valid_two_floor.yaml"))

    result = run_preflight(spec)

    assert "preflight: F2:bed2 is only reachable through bedroom transit" not in result.report.errors
    assert "preflight: F2:bed3 is only reachable through bedroom transit" not in result.report.errors
    assert result.bedroom_violations == ()
