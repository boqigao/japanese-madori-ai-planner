from __future__ import annotations

from plan_engine.models import (
    CoreSpec,
    EnvelopeSpec,
    FloorSolution,
    FloorSpec,
    GridSpec,
    PlanSolution,
    PlanSpec,
    Rect,
    SiteSpec,
    SpaceGeometry,
    SpaceSpec,
    TopologySpec,
    ValidationReport,
)
from plan_engine.validator.livability import validate_livability


def _orientation_spec(north: str) -> PlanSpec:
    return PlanSpec(
        version="0.2",
        units="mm",
        grid=GridSpec(minor=455, major=910),
        site=SiteSpec(envelope=EnvelopeSpec(type="rectangle", width=3640, depth=3640), north=north),
        floors={
            "F1": FloorSpec(
                id="F1",
                core=CoreSpec(stair=None),
                spaces=[
                    SpaceSpec(id="ldk1", type="ldk"),
                    SpaceSpec(id="bed1", type="bedroom"),
                    SpaceSpec(id="wash1", type="washroom"),
                    SpaceSpec(id="stor1", type="storage"),
                ],
                topology=TopologySpec(adjacency=[]),
            )
        },
    )


def test_validate_livability_adds_orientation_warnings_for_unmet_preferences() -> None:
    spec = _orientation_spec(north="top")
    solution = PlanSolution(
        units="mm",
        grid=spec.grid,
        envelope=spec.site.envelope,
        north=spec.site.north,
        floors={
            "F1": FloorSolution(
                id="F1",
                spaces={
                    "ldk1": SpaceGeometry("ldk1", "ldk", [Rect(0, 0, 1820, 1820)]),
                    "bed1": SpaceGeometry("bed1", "bedroom", [Rect(1820, 0, 1820, 1820)]),
                    "wash1": SpaceGeometry("wash1", "washroom", [Rect(0, 1820, 1820, 1820)]),
                    "stor1": SpaceGeometry("stor1", "storage", [Rect(1820, 1820, 1820, 1820)]),
                },
                stair=None,
                topology=[],
            )
        },
    )
    report = ValidationReport()

    validate_livability(spec, solution, report)

    assert any("ldk1 misses south-facing preference" in warning for warning in report.warnings)
    assert any("bed1 misses south-facing preference" in warning for warning in report.warnings)
    assert any("wash1 misses north-facing service preference" in warning for warning in report.warnings)
    assert any("stor1 misses north-facing service preference" in warning for warning in report.warnings)
    assert any("orientation_summary" in diagnostic for diagnostic in report.diagnostics)
    assert any("orientation major_south" in diagnostic for diagnostic in report.diagnostics)
    assert any("orientation service_north" in diagnostic for diagnostic in report.diagnostics)


def test_validate_livability_orientation_success_has_no_orientation_warnings() -> None:
    spec = _orientation_spec(north="top")
    solution = PlanSolution(
        units="mm",
        grid=spec.grid,
        envelope=spec.site.envelope,
        north=spec.site.north,
        floors={
            "F1": FloorSolution(
                id="F1",
                spaces={
                    "ldk1": SpaceGeometry("ldk1", "ldk", [Rect(0, 1820, 1820, 1820)]),
                    "bed1": SpaceGeometry("bed1", "bedroom", [Rect(1820, 1820, 1820, 1820)]),
                    "wash1": SpaceGeometry("wash1", "washroom", [Rect(0, 0, 1820, 1820)]),
                    "stor1": SpaceGeometry("stor1", "storage", [Rect(1820, 0, 1820, 1820)]),
                },
                stair=None,
                topology=[],
            )
        },
    )
    report = ValidationReport()

    validate_livability(spec, solution, report)

    assert not any("south-facing preference" in warning for warning in report.warnings)
    assert not any("north-facing service preference" in warning for warning in report.warnings)
    assert any("major_south=2/2" in diagnostic for diagnostic in report.diagnostics)
    assert any("service_north=2/2" in diagnostic for diagnostic in report.diagnostics)
