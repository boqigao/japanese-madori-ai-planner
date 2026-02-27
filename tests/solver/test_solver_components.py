from __future__ import annotations

from dataclasses import replace

import pytest
from ortools.sat.python import cp_model

from plan_engine.models import AreaConstraint, ShapeSpec, SpaceSpec, StairSpec
from plan_engine.solver.constraints import (
    edge_touch_constraint,
    enforce_exterior_touch,
    enforce_internal_portal_edge,
    enforce_non_adjacent,
    pair_touch_bool,
    touching_constraint,
)
from plan_engine.solver.rect_var import _compute_stair_footprint, _resolve_riser_configuration, new_rect
from plan_engine.solver.space_specs import _component_count, _max_area_cells, _min_area_cells


def _const(model: cp_model.CpModel, value: int, name: str) -> cp_model.IntVar:
    var = model.NewIntVar(value, value, name)
    model.Add(var == value)
    return var


def test_space_component_count_and_area_bounds() -> None:
    hall_l2 = SpaceSpec(id="h1", type="hall", shape=ShapeSpec(allow=["L2"], rect_components_max=4))
    hall_rect_and_l2 = SpaceSpec(id="h2", type="hall", shape=ShapeSpec(allow=["rect", "L2"], rect_components_max=4))
    entry = SpaceSpec(id="e1", type="entry", area=AreaConstraint(target_tatami=4.0))

    assert _component_count(hall_l2) == 4
    assert _component_count(hall_rect_and_l2) == 1
    assert _min_area_cells(entry, 455) > 0
    # Entry hard cap should dominate target area.
    assert _max_area_cells(entry, 455) is not None
    assert _max_area_cells(entry, 455) <= _min_area_cells(SpaceSpec(id="e2", type="entry", area=AreaConstraint(min_tatami=3.0)), 455)


def test_resolve_riser_and_stair_footprint() -> None:
    count, riser = _resolve_riser_configuration(floor_height=2730, riser_pref=230)
    assert count >= 2
    assert abs(count * riser - 2730) <= 2

    straight = StairSpec(
        id="stair",
        type="straight",
        width=910,
        floor_height=2730,
        riser_pref=230,
        tread_pref=210,
        connects={"F1": "h1", "F2": "h2"},
    )
    lshape = replace(straight, type="L_landing")

    fp_straight = _compute_stair_footprint(straight, 455)
    fp_lshape = _compute_stair_footprint(lshape, 455)
    assert fp_straight.w_cells >= 1
    assert len(fp_straight.components) == 1
    assert len(fp_lshape.components) == 3

    with pytest.raises(ValueError, match="unsupported stair type"):
        _compute_stair_footprint(replace(straight, type="unknown"), 455)


def test_touching_and_non_adjacent_constraints() -> None:
    model = cp_model.CpModel()
    # A at x=0..2, B at x=2..4 => touching on vertical edge.
    a = new_rect(model, "a", max_w=8, max_h=8, fixed_w=2, fixed_h=2, shared_x=_const(model, 0, "ax"), shared_y=_const(model, 0, "ay"))
    b = new_rect(model, "b", max_w=8, max_h=8, fixed_w=2, fixed_h=2, shared_x=_const(model, 2, "bx"), shared_y=_const(model, 0, "by"))

    touch_any = touching_constraint(model, [a], [b], max_w=8, max_h=8, prefix="touch", required=True)
    edge_touch = edge_touch_constraint(model, a, [b], edge="right", max_w=8, max_h=8, prefix="edge", required=False)
    enforce_internal_portal_edge(model, a, edge="right", max_w=8, max_h=8)

    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    assert solver.Value(touch_any) == 1
    assert solver.Value(edge_touch) in {0, 1}


def test_non_adjacent_makes_adjacent_layout_infeasible() -> None:
    model = cp_model.CpModel()
    a = new_rect(model, "a", max_w=8, max_h=8, fixed_w=2, fixed_h=2, shared_x=_const(model, 0, "ax"), shared_y=_const(model, 0, "ay"))
    b = new_rect(model, "b", max_w=8, max_h=8, fixed_w=2, fixed_h=2, shared_x=_const(model, 2, "bx"), shared_y=_const(model, 0, "by"))
    enforce_non_adjacent(model, [a], [b], prefix="sep")

    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    assert status == cp_model.INFEASIBLE


def test_exterior_touch_and_invalid_internal_portal_edge() -> None:
    model = cp_model.CpModel()
    # This rect is strictly inside envelope, so exterior touch should make model infeasible.
    r = new_rect(
        model,
        "r",
        max_w=8,
        max_h=8,
        fixed_w=2,
        fixed_h=2,
        shared_x=_const(model, 3, "rx"),
        shared_y=_const(model, 3, "ry"),
    )
    enforce_exterior_touch(model, [r], max_w=8, max_h=8, prefix="ext")

    solver = cp_model.CpSolver()
    assert solver.Solve(model) == cp_model.INFEASIBLE

    with pytest.raises(ValueError, match="unsupported portal edge"):
        enforce_internal_portal_edge(cp_model.CpModel(), r, edge="diag", max_w=8, max_h=8)


def test_pair_touch_bool_detects_non_touching_rects() -> None:
    model = cp_model.CpModel()
    a = new_rect(model, "a", max_w=8, max_h=8, fixed_w=2, fixed_h=2, shared_x=_const(model, 0, "ax"), shared_y=_const(model, 0, "ay"))
    b = new_rect(model, "b", max_w=8, max_h=8, fixed_w=2, fixed_h=2, shared_x=_const(model, 5, "bx"), shared_y=_const(model, 5, "by"))
    touch = pair_touch_bool(model, a, b, max_w=8, max_h=8, prefix="p")

    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    assert solver.Value(touch) == 0
