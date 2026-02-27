from __future__ import annotations

from dataclasses import replace

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
    StairGeometry,
    StairSpec,
    TopologySpec,
    ValidationReport,
)
from plan_engine.validator.connectivity import validate_connectivity
from plan_engine.validator.geometry import validate_entry_exterior, validate_geometry, validate_space_presence
from plan_engine.validator.livability import validate_livability
from plan_engine.validator.stair import validate_stair
from plan_engine.validator.structural import validate_structural


def _simple_spec_with_entry_and_hall() -> PlanSpec:
    return PlanSpec(
        version="0.2",
        units="mm",
        grid=GridSpec(minor=455, major=910),
        site=SiteSpec(envelope=EnvelopeSpec(type="rectangle", width=1820, depth=1820), north="top"),
        floors={
            "F1": FloorSpec(
                id="F1",
                core=CoreSpec(stair=None),
                spaces=[SpaceSpec(id="entry", type="entry"), SpaceSpec(id="hall", type="hall")],
                topology=TopologySpec(adjacency=[("entry", "hall")]),
            )
        },
    )


def test_validate_space_presence_detects_missing_and_extra() -> None:
    spec = _simple_spec_with_entry_and_hall()
    solution = PlanSolution(
        units="mm",
        grid=spec.grid,
        envelope=spec.site.envelope,
        north=spec.site.north,
        floors={
            "F1": FloorSolution(
                id="F1",
                spaces={
                    "entry": SpaceGeometry(id="entry", type="entry", rects=[Rect(0, 0, 455, 455)]),
                    "extra": SpaceGeometry(id="extra", type="storage", rects=[Rect(455, 0, 455, 455)]),
                },
                stair=None,
                topology=[],
            )
        },
    )
    report = ValidationReport()
    validate_space_presence(spec, solution, report)
    assert any("missing spaces" in item for item in report.errors)
    assert any("unexpected spaces" in item for item in report.errors)


def test_validate_geometry_and_entry_exterior_detect_errors() -> None:
    spec = _simple_spec_with_entry_and_hall()
    # Misaligned + overlap + not full coverage + entry not on exterior.
    solution = PlanSolution(
        units="mm",
        grid=spec.grid,
        envelope=spec.site.envelope,
        north=spec.site.north,
        floors={
            "F1": FloorSolution(
                id="F1",
                spaces={
                    "entry": SpaceGeometry(id="entry", type="entry", rects=[Rect(455, 455, 455, 455)]),
                    "hall": SpaceGeometry(id="hall", type="hall", rects=[Rect(455, 455, 500, 455)]),
                },
                stair=None,
                topology=[],
            )
        },
    )
    report = ValidationReport()
    validate_geometry(spec, solution, report)
    validate_entry_exterior(spec, solution, report)
    assert any("not aligned" in item for item in report.errors)
    assert any("overlaps" in item for item in report.errors)
    assert any("area coverage" in item for item in report.errors)
    assert any("entry must touch exterior" in item for item in report.errors)


def test_validate_connectivity_reports_wc_ldk_direct_connection() -> None:
    spec = _simple_spec_with_entry_and_hall()
    _ = spec
    solution = PlanSolution(
        units="mm",
        grid=GridSpec(455, 910),
        envelope=EnvelopeSpec(type="rectangle", width=1820, depth=1820),
        north="top",
        floors={
            "F1": FloorSolution(
                id="F1",
                spaces={
                    "entry": SpaceGeometry("entry", "entry", [Rect(0, 0, 910, 910)]),
                    "wc1": SpaceGeometry("wc1", "toilet", [Rect(910, 0, 910, 910)]),
                    "ldk": SpaceGeometry("ldk", "ldk", [Rect(910, 910, 910, 910)]),
                },
                stair=None,
                topology=[],
            )
        },
    )

    report = ValidationReport()
    validate_connectivity(solution, report)
    assert any("wc1" in item and "ldk" in item for item in report.errors)


def test_validate_stair_detects_portal_mismatch(sample_spec, solved_solution) -> None:
    floor1 = solved_solution.floors["F1"]
    assert floor1.stair is not None
    bad_stair = replace(
        floor1.stair,
        portal_edge="left" if floor1.stair.portal_edge != "left" else "right",
    )
    bad_solution = replace(
        solved_solution,
        floors={**solved_solution.floors, "F1": replace(floor1, stair=bad_stair)},
    )

    report = ValidationReport()
    validate_stair(sample_spec, bad_solution, report)
    assert any("portal edge mismatch" in item for item in report.errors)


def test_validate_livability_and_structural_sections() -> None:
    spec = PlanSpec(
        version="0.2",
        units="mm",
        grid=GridSpec(minor=455, major=910),
        site=SiteSpec(envelope=EnvelopeSpec(type="rectangle", width=3640, depth=3640), north="top"),
        floors={
            "F1": FloorSpec(
                id="F1",
                core=CoreSpec(stair=None),
                spaces=[
                    SpaceSpec(id="entry", type="entry"),
                    SpaceSpec(id="bed1", type="bedroom"),
                    SpaceSpec(id="bath1", type="bath"),
                ],
                topology=TopologySpec(adjacency=[]),
            )
        },
    )
    solution = PlanSolution(
        units="mm",
        grid=spec.grid,
        envelope=spec.site.envelope,
        north="top",
        floors={
            "F1": FloorSolution(
                id="F1",
                spaces={
                    "entry": SpaceGeometry("entry", "entry", [Rect(0, 0, 910, 910)]),
                    "bed1": SpaceGeometry("bed1", "bedroom", [Rect(910, 0, 910, 1820)]),
                    "bath1": SpaceGeometry("bath1", "bath", [Rect(1820, 0, 1820, 1820)]),
                },
                stair=None,
                topology=[],
            )
        },
    )

    report = ValidationReport()
    validate_livability(spec, solution, report)
    validate_structural(spec, solution, report)

    assert any("bath exists without washroom" in item for item in report.errors)
    assert report.structural


def test_validate_stair_warns_when_no_stair_declared() -> None:
    spec = _simple_spec_with_entry_and_hall()
    solution = PlanSolution(
        units="mm",
        grid=spec.grid,
        envelope=spec.site.envelope,
        north=spec.site.north,
        floors={
            "F1": FloorSolution(
                id="F1",
                spaces={
                    "entry": SpaceGeometry(id="entry", type="entry", rects=[Rect(0, 0, 910, 1820)]),
                    "hall": SpaceGeometry(id="hall", type="hall", rects=[Rect(910, 0, 910, 1820)]),
                },
                stair=None,
                topology=[("entry", "hall")],
            )
        },
    )
    report = ValidationReport()
    validate_stair(spec, solution, report)
    assert any("no stair declared" in item for item in report.warnings)


def test_validate_stair_alignment_error_on_two_floors() -> None:
    stair_spec = StairSpec(
        id="stair",
        type="straight",
        width=910,
        floor_height=2730,
        riser_pref=230,
        tread_pref=210,
        connects={"F1": "h1", "F2": "h2"},
    )
    spec = PlanSpec(
        version="0.2",
        units="mm",
        grid=GridSpec(minor=455, major=910),
        site=SiteSpec(envelope=EnvelopeSpec(type="rectangle", width=3640, depth=3640), north="top"),
        floors={
            "F1": FloorSpec(id="F1", core=CoreSpec(stair=stair_spec), spaces=[SpaceSpec(id="h1", type="hall")]),
            "F2": FloorSpec(id="F2", core=CoreSpec(stair=stair_spec), spaces=[SpaceSpec(id="h2", type="hall")]),
        },
    )

    stair_f1 = StairGeometry(
        id="stair",
        type="straight",
        bbox=Rect(910, 910, 910, 1820),
        components=[Rect(910, 910, 910, 1820)],
        floor_height=2730,
        riser_count=12,
        tread_count=11,
        riser_mm=228,
        tread_mm=210,
        landing_size=(910, 910),
        connects={"F1": "h1", "F2": "h2"},
        portal_component=0,
        portal_edge="top",
    )
    stair_f2 = replace(stair_f1, bbox=Rect(1365, 910, 910, 1820), components=[Rect(1365, 910, 910, 1820)])

    solution = PlanSolution(
        units="mm",
        grid=spec.grid,
        envelope=spec.site.envelope,
        north="top",
        floors={
            "F1": FloorSolution(
                id="F1",
                spaces={"h1": SpaceGeometry("h1", "hall", [Rect(0, 910, 910, 1820)])},
                stair=stair_f1,
                topology=[("h1", "stair")],
            ),
            "F2": FloorSolution(
                id="F2",
                spaces={"h2": SpaceGeometry("h2", "hall", [Rect(0, 910, 910, 1820)])},
                stair=stair_f2,
                topology=[("h2", "stair")],
            ),
        },
    )

    report = ValidationReport()
    validate_stair(spec, solution, report)
    assert any("projection is not aligned" in item for item in report.errors)
