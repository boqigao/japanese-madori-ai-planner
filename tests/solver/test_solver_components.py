from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from ortools.sat.python import cp_model

from plan_engine.dsl import load_plan_spec
from plan_engine.models import (
    AdjacencyRule,
    AreaConstraint,
    BuildableRectSpec,
    CoreSpec,
    EnvelopeSpec,
    FloorSpec,
    GridSpec,
    PlanSpec,
    ShapeSpec,
    SiteSpec,
    SizeConstraints,
    SpaceSpec,
    StairSpec,
    TopologySpec,
)
from plan_engine.solver import PlanSolver
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
    uturn = replace(straight, type="U_turn")

    fp_straight = _compute_stair_footprint(straight, 455)
    fp_lshape = _compute_stair_footprint(lshape, 455)
    fp_uturn = _compute_stair_footprint(uturn, 455)
    assert fp_straight.w_cells >= 1
    assert len(fp_straight.components) == 1
    assert len(fp_lshape.components) == 3
    assert len(fp_uturn.components) == 3
    assert fp_uturn.w_cells == 2 * (straight.width // 455)
    assert fp_uturn.components[1][0] == "landing"

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


def _single_floor_wet_spec(include_toilet_hall_edge: bool, include_wet_hall_edge: bool = True) -> PlanSpec:
    adjacency = [
        AdjacencyRule(left_id="wash1", right_id="bath1", strength="required"),
        AdjacencyRule(left_id="hall1", right_id="storage1", strength="required"),
    ]
    if include_wet_hall_edge:
        adjacency.insert(0, AdjacencyRule(left_id="hall1", right_id="wash1", strength="required"))
    if include_toilet_hall_edge:
        adjacency.insert(0, AdjacencyRule(left_id="toilet1", right_id="hall1", strength="required"))
    return PlanSpec(
        version="0.2",
        units="mm",
        grid=GridSpec(minor=455, major=910),
        site=SiteSpec(envelope=EnvelopeSpec(type="rectangle", width=5460, depth=4550), north="top"),
        floors={
            "F1": FloorSpec(
                id="F1",
                core=CoreSpec(stair=None),
                spaces=[
                    SpaceSpec(id="hall1", type="hall", shape=ShapeSpec(allow=["L2"], rect_components_max=4)),
                    SpaceSpec(id="toilet1", type="toilet"),
                    SpaceSpec(id="wash1", type="washroom"),
                    SpaceSpec(id="bath1", type="bath"),
                    SpaceSpec(id="storage1", type="storage"),
                ],
                topology=TopologySpec(adjacency=adjacency),
            )
        },
    )


def _major_room_exterior_spec(buildable_x_mm: int) -> PlanSpec:
    """Build a single-floor spec for exterior-touch feasibility testing.

    Args:
        buildable_x_mm: X offset of the indoor buildable rectangle in mm.
            ``0`` means touching exterior; ``>0`` means detached from exterior.

    Returns:
        PlanSpec with one hall and one bedroom covering a constrained floor.
    """
    return PlanSpec(
        version="0.2",
        units="mm",
        grid=GridSpec(minor=455, major=910),
        site=SiteSpec(envelope=EnvelopeSpec(type="rectangle", width=5460, depth=5460), north="top"),
        floors={
            "F1": FloorSpec(
                id="F1",
                core=CoreSpec(stair=None),
                buildable_mask=[BuildableRectSpec(buildable_x_mm, 455, 4550, 4550)],
                spaces=[
                    SpaceSpec(id="hall1", type="hall", area=AreaConstraint(min_tatami=3.0, target_tatami=4.0)),
                    SpaceSpec(
                        id="bed1",
                        type="bedroom",
                        size_constraints=SizeConstraints(min_width=1820),
                        area=AreaConstraint(min_tatami=6.0, target_tatami=7.0),
                    ),
                ],
                topology=TopologySpec(adjacency=[AdjacencyRule("hall1", "bed1", "required")]),
            )
        },
    )


def test_solver_realizes_declared_toilet_circulation_edge() -> None:
    spec = _single_floor_wet_spec(include_toilet_hall_edge=True)

    solution = PlanSolver(max_time_seconds=10.0, num_workers=2).solve(spec)

    floor = solution.floors["F1"]
    toilet_rects = floor.spaces["toilet1"].rects
    hall_rects = floor.spaces["hall1"].rects
    assert any(toilet.shares_edge_with(hall) for toilet in toilet_rects for hall in hall_rects)


def test_solver_rejects_toilet_without_circulation_topology_edge() -> None:
    spec = _single_floor_wet_spec(include_toilet_hall_edge=False)

    with pytest.raises(ValueError, match="requires topology adjacency to hall/entry/stair"):
        PlanSolver(max_time_seconds=10.0, num_workers=2).solve(spec)


def test_solver_rejects_wet_core_without_circulation_topology_edge() -> None:
    spec = _single_floor_wet_spec(include_toilet_hall_edge=True, include_wet_hall_edge=False)

    with pytest.raises(ValueError, match="wet core requires topology adjacency to hall/entry/stair"):
        PlanSolver(max_time_seconds=10.0, num_workers=2).solve(spec)


def test_solver_rejects_interior_only_major_room_buildable() -> None:
    spec = _major_room_exterior_spec(buildable_x_mm=455)

    with pytest.raises(RuntimeError, match="unable to produce a valid plan"):
        PlanSolver(max_time_seconds=10.0, num_workers=2).solve(spec)


def test_solver_places_major_room_on_exterior_when_feasible() -> None:
    spec = _major_room_exterior_spec(buildable_x_mm=0)

    solution = PlanSolver(max_time_seconds=10.0, num_workers=2).solve(spec)

    floor = solution.floors["F1"]
    bedroom = floor.spaces["bed1"]
    assert any(
        rect.x == 0
        or rect.y == 0
        or rect.x2 == spec.site.envelope.width
        or rect.y2 == spec.site.envelope.depth
        for rect in bedroom.rects
    )


def test_solver_major_room_exterior_success_fixture_is_satisfiable() -> None:
    fixture = Path(__file__).resolve().parents[2] / "resources" / "specs" / "major_room_exterior_valid.yaml"
    spec = load_plan_spec(fixture)

    solution = PlanSolver(max_time_seconds=10.0, num_workers=2).solve(spec)

    bedroom = solution.floors["F1"].spaces["bed1"]
    assert any(rect.x == 0 or rect.y == 0 for rect in bedroom.rects)


def _compact_wet_spec(include_washstand: bool) -> PlanSpec:
    """Build a single-floor spec with compact wet types (shower ± washstand)."""
    spaces = [
        SpaceSpec(id="hall1", type="hall", shape=ShapeSpec(allow=["L2"], rect_components_max=4)),
        SpaceSpec(id="shower1", type="shower"),
        SpaceSpec(id="storage1", type="storage"),
    ]
    adjacency = [
        AdjacencyRule(left_id="hall1", right_id="storage1", strength="required"),
    ]
    if include_washstand:
        spaces.insert(2, SpaceSpec(id="ws1", type="washstand"))
        adjacency.extend([
            AdjacencyRule(left_id="hall1", right_id="ws1", strength="required"),
            AdjacencyRule(left_id="ws1", right_id="shower1", strength="required"),
        ])
    else:
        adjacency.append(AdjacencyRule(left_id="hall1", right_id="shower1", strength="required"))
    return PlanSpec(
        version="0.2",
        units="mm",
        grid=GridSpec(minor=455, major=910),
        site=SiteSpec(envelope=EnvelopeSpec(type="rectangle", width=5460, depth=4550), north="top"),
        floors={
            "F1": FloorSpec(
                id="F1",
                core=CoreSpec(stair=None),
                spaces=spaces,
                topology=TopologySpec(adjacency=adjacency),
            )
        },
    )


def test_solver_rejects_shower_without_washstand() -> None:
    spec = _compact_wet_spec(include_washstand=False)
    with pytest.raises(ValueError, match="shower but no washstand"):
        PlanSolver(max_time_seconds=10.0, num_workers=2).solve(spec)


class TestBedroomAspectRatioConstraint:
    """Verify the bedroom aspect ratio hard constraint (max 1:1.80)."""

    @staticmethod
    def _check_feasibility(w_cells: int, h_cells: int) -> bool:
        """Return True if a rect with given w/h satisfies 5*w<=9*h and 5*h<=9*w."""
        model = cp_model.CpModel()
        w = model.NewIntVar(w_cells, w_cells, "w")
        h = model.NewIntVar(h_cells, h_cells, "h")
        model.Add(5 * w <= 9 * h)
        model.Add(5 * h <= 9 * w)
        solver = cp_model.CpSolver()
        return solver.Solve(model) == cp_model.OPTIMAL

    def test_square_bedroom_accepted(self) -> None:
        assert self._check_feasibility(8, 8)  # 3640x3640, ratio 1:1.00

    def test_standard_6jo_accepted(self) -> None:
        assert self._check_feasibility(6, 8)  # 2730x3640, ratio 1:1.33

    def test_compact_boundary_accepted(self) -> None:
        assert self._check_feasibility(5, 9)  # 2275x4095, ratio 1:1.80

    def test_elongated_rejected(self) -> None:
        assert not self._check_feasibility(5, 12)  # 2275x5460, ratio 1:2.40

    def test_corridor_rejected(self) -> None:
        assert not self._check_feasibility(4, 10)  # 1820x4550, ratio 1:2.50
