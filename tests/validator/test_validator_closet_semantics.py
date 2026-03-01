from __future__ import annotations

from plan_engine.models import (
    CoreSpec,
    EmbeddedClosetGeometry,
    EmbeddedClosetSpec,
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
from plan_engine.validator.connectivity import validate_connectivity
from plan_engine.validator.geometry import validate_geometry


def test_validate_connectivity_flags_wic_without_parent_topology_access() -> None:
    solution = PlanSolution(
        units="mm",
        grid=GridSpec(455, 910),
        envelope=EnvelopeSpec(type="rectangle", width=3640, depth=2730),
        north="top",
        floors={
            "F1": FloorSolution(
                id="F1",
                spaces={
                    "entry": SpaceGeometry("entry", "entry", [Rect(0, 0, 910, 1820)]),
                    "hall1": SpaceGeometry("hall1", "hall", [Rect(910, 0, 910, 1820)]),
                    "master": SpaceGeometry("master", "master_bedroom", [Rect(1820, 0, 1820, 1820)]),
                    "wic1": SpaceGeometry(
                        "wic1",
                        "wic",
                        [Rect(1820, 1820, 910, 910)],
                        parent_id="master",
                    ),
                },
                stair=None,
                topology=[("entry", "hall1"), ("hall1", "master")],
            )
        },
    )

    report = ValidationReport()
    validate_connectivity(solution, report)

    assert any("missing topology edge to parent" in item for item in report.errors)
    assert any("parent edge" in item for item in report.errors)
    assert any("walk-in closet has no realized access edge" in item for item in report.errors)


def test_validate_geometry_flags_closet_parent_mismatch() -> None:
    spec = PlanSpec(
        version="0.2",
        units="mm",
        grid=GridSpec(minor=455, major=910),
        site=SiteSpec(
            envelope=EnvelopeSpec(type="rectangle", width=4550, depth=1820),
            north="top",
        ),
        floors={
            "F1": FloorSpec(
                id="F1",
                core=CoreSpec(stair=None),
                spaces=[
                    SpaceSpec(id="entry", type="entry"),
                    SpaceSpec(id="hall1", type="hall"),
                    SpaceSpec(id="bed1", type="bedroom"),
                    SpaceSpec(id="storage1", type="storage"),
                ],
                embedded_closets=[EmbeddedClosetSpec(id="closet1", parent_id="bed1")],
                topology=TopologySpec(adjacency=[]),
            )
        },
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
                    "entry": SpaceGeometry("entry", "entry", [Rect(0, 0, 910, 1820)]),
                    "hall1": SpaceGeometry("hall1", "hall", [Rect(910, 0, 910, 1820)]),
                    "bed1": SpaceGeometry("bed1", "bedroom", [Rect(1820, 0, 910, 1820)]),
                    "storage1": SpaceGeometry("storage1", "storage", [Rect(2730, 0, 910, 1820)]),
                },
                embedded_closets=[
                    EmbeddedClosetGeometry(
                        id="closet1",
                        parent_id="bed1",
                        rect=Rect(3640, 0, 910, 1820),
                    )
                ],
                stair=None,
                topology=[],
            )
        },
    )

    report = ValidationReport()
    validate_geometry(spec, solution, report)

    assert any("is not inside parent 'bed1'" in item for item in report.errors)
