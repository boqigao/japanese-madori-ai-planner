from __future__ import annotations

from pathlib import Path

from plan_engine.dsl import load_plan_spec
from plan_engine.models import (
    AdjacencyRule,
    AreaConstraint,
    CoreSpec,
    EmbeddedClosetSpec,
    FloorSpec,
    GridSpec,
    PlanSpec,
    ShapeSpec,
    SizeConstraints,
    SiteSpec,
    SpaceSpec,
    TopologySpec,
    ValidationReport,
)
from plan_engine.models.spec import BuildableRectSpec, EnvelopeSpec
from plan_engine.preflight import run_preflight
from plan_engine.preflight.closets import _warn_closet_wall_feasibility


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


def _make_simple_spec(
    spaces: list[SpaceSpec],
    adjacency: list[AdjacencyRule],
    closets: list[EmbeddedClosetSpec] | None = None,
) -> PlanSpec:
    """Build a minimal PlanSpec with one floor for closet feasibility testing."""
    return PlanSpec(
        version="0.2",
        units="mm",
        grid=GridSpec(minor=455, major=910),
        site=SiteSpec(
            envelope=EnvelopeSpec(type="rectangle", width=9100, depth=5460),
            north="top",
        ),
        floors={
            "F1": FloorSpec(
                id="F1",
                core=CoreSpec(stair=None),
                spaces=spaces,
                embedded_closets=closets or [],
                topology=TopologySpec(adjacency=adjacency),
                buildable_mask=[BuildableRectSpec(x=0, y=0, w=9100, h=5460)],
            )
        },
    )


def _make_space(id: str, type: str) -> SpaceSpec:
    return SpaceSpec(
        id=id, type=type, space_class="indoor",
        area=AreaConstraint(), size_constraints=SizeConstraints(), shape=ShapeSpec(),
    )


def test_closet_wall_feasibility_no_warning_when_not_all_doors() -> None:
    """Bedroom with mixed neighbors (bedroom + hall) should not warn."""
    spec = _make_simple_spec(
        spaces=[_make_space("br1", "bedroom"), _make_space("hall", "hall"), _make_space("br2", "bedroom")],
        adjacency=[
            AdjacencyRule(left_id="br1", right_id="hall", strength="auto"),
            AdjacencyRule(left_id="br1", right_id="br2", strength="auto"),
        ],
        closets=[EmbeddedClosetSpec(id="cl1", parent_id="br1", area=AreaConstraint(target_tatami=1.0))],
    )
    report = ValidationReport()
    _warn_closet_wall_feasibility(spec, "F1", report)
    assert not any("closet may conflict" in w for w in report.warnings)


def test_closet_wall_feasibility_warns_when_all_neighbors_have_doors() -> None:
    """Bedroom with only hall + ldk + washroom neighbors — all produce doors."""
    spec = _make_simple_spec(
        spaces=[
            _make_space("br1", "bedroom"),
            _make_space("hall", "hall"),
            _make_space("ldk", "ldk"),
            _make_space("wash1", "washroom"),
        ],
        adjacency=[
            AdjacencyRule(left_id="br1", right_id="hall", strength="auto"),
            AdjacencyRule(left_id="br1", right_id="ldk", strength="auto"),
            AdjacencyRule(left_id="br1", right_id="wash1", strength="auto"),
        ],
        closets=[EmbeddedClosetSpec(id="cl1", parent_id="br1", area=AreaConstraint(target_tatami=1.0))],
    )
    report = ValidationReport()
    _warn_closet_wall_feasibility(spec, "F1", report)
    assert any("closet may conflict" in w for w in report.warnings)
