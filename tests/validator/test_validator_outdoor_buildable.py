from __future__ import annotations

from plan_engine.models import (
    EnvelopeSpec,
    FloorSolution,
    GridSpec,
    PlanSolution,
    PlanSpec,
    Rect,
    SiteSpec,
    SpaceGeometry,
    ValidationReport,
)
from plan_engine.validator.connectivity import validate_connectivity
from plan_engine.validator.geometry import validate_geometry


def _base_solution() -> PlanSolution:
    return PlanSolution(
        units="mm",
        grid=GridSpec(455, 910),
        envelope=EnvelopeSpec(type="rectangle", width=3640, depth=2730),
        north="top",
        floors={
            "F1": FloorSolution(
                id="F1",
                spaces={
                    "entry": SpaceGeometry("entry", "entry", [Rect(0, 0, 910, 1365)], "indoor"),
                    "hall1": SpaceGeometry("hall1", "hall", [Rect(910, 0, 910, 2730)], "indoor"),
                    "storage1": SpaceGeometry("storage1", "storage", [Rect(1820, 0, 910, 2730)], "indoor"),
                    "balcony1": SpaceGeometry("balcony1", "balcony", [Rect(2730, 1365, 910, 1365)], "outdoor"),
                },
                stair=None,
                topology=[("entry", "hall1"), ("hall1", "storage1"), ("hall1", "balcony1")],
                buildable_mask=[Rect(0, 0, 2730, 2730)],
                indoor_buildable_area_mm2=2730 * 2730,
            )
        },
    )


def test_validate_geometry_reports_indoor_buildable_coverage_gap() -> None:
    spec = PlanSpec(
        version="0.2",
        units="mm",
        grid=GridSpec(455, 910),
        site=SiteSpec(envelope=EnvelopeSpec(type="rectangle", width=3640, depth=2730), north="top"),
        floors={},
    )
    solution = _base_solution()
    # Remove part of indoor coverage so indoor area < buildable area.
    solution.floors["F1"].spaces["storage1"] = SpaceGeometry(
        "storage1", "storage", [Rect(1820, 0, 910, 1365)], "indoor"
    )

    report = ValidationReport()
    validate_geometry(spec, solution, report)

    assert any("indoor area coverage must be 100% of buildable mask" in item for item in report.errors)


def test_validate_connectivity_reports_unrealized_outdoor_access() -> None:
    solution = _base_solution()
    # Break realized touch while keeping topology declaration.
    solution.floors["F1"].spaces["balcony1"] = SpaceGeometry(
        "balcony1", "balcony", [Rect(2730, 0, 910, 910)], "outdoor"
    )

    report = ValidationReport()
    validate_connectivity(solution, report)

    assert any("outdoor access topology is declared but not physically realized" in item for item in report.errors)


def test_validate_geometry_reports_major_room_without_exterior_touch() -> None:
    spec = PlanSpec(
        version="0.2",
        units="mm",
        grid=GridSpec(455, 910),
        site=SiteSpec(envelope=EnvelopeSpec(type="rectangle", width=3640, depth=3640), north="top"),
        floors={},
    )
    solution = PlanSolution(
        units="mm",
        grid=spec.grid,
        envelope=spec.site.envelope,
        north=spec.site.north,
        floors={
            "F1": FloorSolution(
                id="F1",
                spaces={
                    "hall1": SpaceGeometry(
                        "hall1",
                        "hall",
                        [
                            Rect(0, 0, 3640, 910),
                            Rect(0, 2730, 3640, 910),
                            Rect(0, 910, 910, 1820),
                            Rect(2730, 910, 910, 1820),
                        ],
                    ),
                    "bed1": SpaceGeometry("bed1", "bedroom", [Rect(910, 910, 1820, 1820)]),
                },
                stair=None,
                topology=[("hall1", "bed1")],
            )
        },
    )

    report = ValidationReport()
    validate_geometry(spec, solution, report)

    assert any(
        "F1:bed1 (bedroom) must touch exterior boundary with positive edge length" in item
        for item in report.errors
    )


def test_validate_geometry_accepts_multi_rect_ldk_when_any_component_touches_exterior() -> None:
    spec = PlanSpec(
        version="0.2",
        units="mm",
        grid=GridSpec(455, 910),
        site=SiteSpec(envelope=EnvelopeSpec(type="rectangle", width=3640, depth=1820), north="top"),
        floors={},
    )
    solution = PlanSolution(
        units="mm",
        grid=spec.grid,
        envelope=spec.site.envelope,
        north=spec.site.north,
        floors={
            "F1": FloorSolution(
                id="F1",
                spaces={
                    "ldk": SpaceGeometry(
                        "ldk",
                        "ldk",
                        [
                            Rect(0, 0, 1820, 910),
                            Rect(910, 910, 910, 910),
                        ],
                    ),
                    "hall1": SpaceGeometry(
                        "hall1",
                        "hall",
                        [
                            Rect(1820, 0, 1820, 910),
                            Rect(0, 910, 910, 910),
                            Rect(1820, 910, 1820, 910),
                        ],
                    ),
                },
                stair=None,
                topology=[("hall1", "ldk")],
            )
        },
    )

    report = ValidationReport()
    validate_geometry(spec, solution, report)

    assert not any("(ldk) must touch exterior boundary with positive edge length" in item for item in report.errors)
