from __future__ import annotations

from pathlib import Path

from plan_engine.dsl import load_plan_spec
from plan_engine.preflight import run_preflight


def _fixture_path(name: str) -> Path:
    return Path(__file__).resolve().parents[2] / "resources" / "specs" / name


def test_preflight_reports_invalid_wic_parent_type() -> None:
    spec = load_plan_spec(_fixture_path("preflight_wic_invalid_parent.yaml"))

    result = run_preflight(spec)

    assert any("wic parent 'ldk' must be bedroom/master_bedroom" in err for err in result.report.errors)


def test_preflight_reports_wic_missing_access_topology() -> None:
    spec = load_plan_spec(_fixture_path("preflight_wic_missing_access.yaml"))

    result = run_preflight(spec)

    assert any("must declare topology adjacency to parent 'bed1'" in err for err in result.report.errors)
    assert any("has no candidate access declaration" in err for err in result.report.errors)


def test_preflight_warns_when_bedroom_has_no_closet_or_wic() -> None:
    spec = load_plan_spec(_fixture_path("preflight_bedroom_transit_valid_two_floor.yaml"))

    result = run_preflight(spec)

    assert any("has no associated closet or WIC" in warning for warning in result.report.warnings)
