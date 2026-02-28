from __future__ import annotations

from dataclasses import replace

import pytest

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
from plan_engine.stair_logic import ordered_floor_ids, stair_portal_for_floor


def test_rect_geometry_helpers() -> None:
    a = Rect(x=0, y=0, w=910, h=910)
    b = Rect(x=910, y=0, w=910, h=910)
    c = Rect(x=455, y=455, w=910, h=910)

    assert a.area == 910 * 910
    assert a.shares_edge_with(b)
    assert not a.overlaps(b)
    assert a.overlaps(c)
    assert a.shared_edge_segment(b) == ((910, 0), (910, 910))


def test_validation_report_text_sections() -> None:
    report = ValidationReport(errors=["e1"], warnings=["w1"], structural=["s1"])
    text = report.to_text()
    assert "valid=False" in text
    assert "Errors:" in text
    assert "Warnings:" in text
    assert "Structural:" in text


def test_solution_to_dict_contains_structural_fields() -> None:
    floor = FloorSolution(
        id="F1",
        spaces={"entry": SpaceGeometry(id="entry", type="entry", rects=[Rect(0, 0, 910, 910)])},
        stair=None,
        topology=[],
    )
    solution = PlanSolution(
        units="mm",
        grid=GridSpec(minor=455, major=910),
        envelope=EnvelopeSpec(type="rectangle", width=1820, depth=1820),
        north="top",
        floors={"F1": floor},
    )
    payload = solution.to_dict()
    assert payload["units"] == "mm"
    assert "floors" in payload


def test_ordered_floor_ids_and_portal_mapping() -> None:
    assert ordered_floor_ids(["F2", "F10", "F1"]) == ["F1", "F2", "F10"]

    portal_f1 = stair_portal_for_floor("straight", floor_index=0, floor_count=2, component_count=1)
    portal_f2 = stair_portal_for_floor("straight", floor_index=1, floor_count=2, component_count=1)
    assert portal_f1.edge == "top"
    assert portal_f2.edge == "bottom"

    l0 = stair_portal_for_floor("L_landing", floor_index=0, floor_count=2, component_count=3)
    l1 = stair_portal_for_floor("L_landing", floor_index=1, floor_count=2, component_count=3)
    assert (l0.component_index, l0.edge) == (0, "left")
    assert (l1.component_index, l1.edge) == (2, "bottom")

    u0 = stair_portal_for_floor("U_turn", floor_index=0, floor_count=2, component_count=3)
    u1 = stair_portal_for_floor("U_turn", floor_index=1, floor_count=2, component_count=3)
    assert (u0.component_index, u0.edge) == (0, "left")
    assert (u1.component_index, u1.edge) == (2, "right")


@pytest.mark.parametrize("floor_count,floor_index", [(3, 0), (2, 2), (2, -1)])
def test_stair_portal_invalid_args(floor_count: int, floor_index: int) -> None:
    with pytest.raises(ValueError):
        stair_portal_for_floor("straight", floor_index=floor_index, floor_count=floor_count, component_count=1)


def test_stair_portal_rejects_unknown_type() -> None:
    with pytest.raises(ValueError, match="unsupported stair type"):
        stair_portal_for_floor("spiral", floor_index=0, floor_count=2, component_count=3)


def test_plan_spec_with_mismatched_stair_ids_triggers_global_stair_error() -> None:
    from plan_engine.solver.rect_var import _find_global_stair

    stair_a = StairSpec(
        id="stair_a",
        type="straight",
        width=910,
        floor_height=2730,
        riser_pref=230,
        tread_pref=210,
        connects={"F1": "h1", "F2": "h2"},
    )
    stair_b = replace(stair_a, id="stair_b")

    spec = PlanSpec(
        version="0.2",
        units="mm",
        grid=GridSpec(minor=455, major=910),
        site=SiteSpec(envelope=EnvelopeSpec(type="rectangle", width=3640, depth=3640), north="top"),
        floors={
            "F1": FloorSpec(id="F1", core=CoreSpec(stair=stair_a), spaces=[SpaceSpec(id="h1", type="hall")]),
            "F2": FloorSpec(id="F2", core=CoreSpec(stair=stair_b), spaces=[SpaceSpec(id="h2", type="hall")]),
        },
    )

    with pytest.raises(ValueError, match="one shared stair id"):
        _find_global_stair(spec)


def test_stair_geometry_to_dict() -> None:
    stair = StairGeometry(
        id="stair",
        type="straight",
        bbox=Rect(0, 0, 910, 1820),
        components=[Rect(0, 0, 910, 1820)],
        floor_height=2730,
        riser_count=12,
        tread_count=11,
        riser_mm=228,
        tread_mm=210,
        landing_size=(910, 910),
        connects={"F1": "hall1", "F2": "hall2"},
        portal_component=0,
        portal_edge="top",
    )
    payload = stair.to_dict()
    assert payload["portal"]["edge"] == "top"
