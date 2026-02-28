from __future__ import annotations

import pytest
from ortools.sat.python import cp_model

from plan_engine.solver.rect_var import new_rect
from plan_engine.solver.space_specs import _north_preference_weight, _south_preference_weight
from plan_engine.solver.workflow import _space_edge_touch_bool, resolve_north_south_edges


def _const(model: cp_model.CpModel, value: int, name: str) -> cp_model.IntVar:
    var = model.NewIntVar(value, value, name)
    model.Add(var == value)
    return var


def test_resolve_north_south_edges_mapping() -> None:
    assert resolve_north_south_edges("top") == ("top", "bottom")
    assert resolve_north_south_edges("right") == ("right", "left")
    assert resolve_north_south_edges("bottom") == ("bottom", "top")
    assert resolve_north_south_edges("left") == ("left", "right")

    with pytest.raises(ValueError, match="unsupported site.north"):
        resolve_north_south_edges("northeast")


def test_orientation_penalty_prefers_south_for_major_room() -> None:
    model = cp_model.CpModel()
    rect = new_rect(
        model=model,
        prefix="bed",
        max_w=6,
        max_h=6,
        fixed_w=2,
        fixed_h=2,
        shared_x=_const(model, 2, "x"),
    )
    top_choice = model.NewBoolVar("top_choice")
    model.Add(rect.y == 0).OnlyEnforceIf(top_choice)
    model.Add(rect.y == 4).OnlyEnforceIf(top_choice.Not())

    south_touch = _space_edge_touch_bool(
        model=model,
        rects=[rect],
        edge="bottom",
        envelope_w_cells=6,
        envelope_h_cells=6,
        prefix="bedroom",
    )
    missing_south = model.NewBoolVar("missing_south")
    model.Add(missing_south + south_touch == 1)
    model.Minimize(_south_preference_weight("bedroom") * missing_south)

    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    assert solver.Value(south_touch) == 1
    assert solver.Value(top_choice) == 0


def test_orientation_penalty_prefers_north_for_service_room() -> None:
    model = cp_model.CpModel()
    rect = new_rect(
        model=model,
        prefix="wash",
        max_w=6,
        max_h=6,
        fixed_w=2,
        fixed_h=2,
        shared_x=_const(model, 2, "x"),
    )
    top_choice = model.NewBoolVar("top_choice")
    model.Add(rect.y == 0).OnlyEnforceIf(top_choice)
    model.Add(rect.y == 4).OnlyEnforceIf(top_choice.Not())

    north_touch = _space_edge_touch_bool(
        model=model,
        rects=[rect],
        edge="top",
        envelope_w_cells=6,
        envelope_h_cells=6,
        prefix="washroom",
    )
    missing_north = model.NewBoolVar("missing_north")
    model.Add(missing_north + north_touch == 1)
    model.Minimize(_north_preference_weight("washroom") * missing_north)

    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    assert solver.Value(north_touch) == 1
    assert solver.Value(top_choice) == 1
