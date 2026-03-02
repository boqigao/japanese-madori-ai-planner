from __future__ import annotations

from plan_engine.models import (
    AdjacencyRule,
    AreaConstraint,
    CoreSpec,
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
from plan_engine.preflight.wet import _check_shower_requires_washstand


def _make_space(id: str, type: str) -> SpaceSpec:
    return SpaceSpec(
        id=id, type=type, space_class="indoor",
        area=AreaConstraint(), size_constraints=SizeConstraints(), shape=ShapeSpec(),
    )


def _make_spec(spaces: list[SpaceSpec], adjacency: list[AdjacencyRule] | None = None) -> PlanSpec:
    """Build a minimal single-floor PlanSpec for wet preflight testing."""
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
                embedded_closets=[],
                topology=TopologySpec(adjacency=adjacency or []),
                buildable_mask=[BuildableRectSpec(x=0, y=0, w=9100, h=5460)],
            )
        },
    )


def test_shower_without_washstand_produces_error() -> None:
    """Floor with shower but no washstand should produce a preflight error."""
    spec = _make_spec(
        spaces=[_make_space("entry", "entry"), _make_space("sh1", "shower")],
    )
    report = ValidationReport()
    _check_shower_requires_washstand(spec, "F1", report)
    assert any("shower" in err and "washstand" in err for err in report.errors)


def test_shower_with_washstand_no_error() -> None:
    """Floor with both shower and washstand should pass."""
    spec = _make_spec(
        spaces=[
            _make_space("entry", "entry"),
            _make_space("ws1", "washstand"),
            _make_space("sh1", "shower"),
        ],
    )
    report = ValidationReport()
    _check_shower_requires_washstand(spec, "F1", report)
    assert not report.errors


def test_no_shower_no_error() -> None:
    """Floor without shower should pass regardless of washstand."""
    spec = _make_spec(spaces=[_make_space("entry", "entry")])
    report = ValidationReport()
    _check_shower_requires_washstand(spec, "F1", report)
    assert not report.errors


def test_compact_wet_cluster_fit_integrated() -> None:
    """Washstand+shower should pass wet cluster fit within full envelope via run_preflight."""
    spec = _make_spec(
        spaces=[
            _make_space("entry", "entry"),
            _make_space("hall", "hall"),
            _make_space("ws1", "washstand"),
            _make_space("sh1", "shower"),
        ],
        adjacency=[
            AdjacencyRule(left_id="entry", right_id="hall", strength="required"),
            AdjacencyRule(left_id="hall", right_id="ws1", strength="required"),
            AdjacencyRule(left_id="ws1", right_id="sh1", strength="required"),
        ],
    )
    result = run_preflight(spec)
    assert not any("wet core cannot form" in err for err in result.report.errors)
    assert not any("shower" in err and "washstand" in err for err in result.report.errors)
