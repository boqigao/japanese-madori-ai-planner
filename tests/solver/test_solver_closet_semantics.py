from __future__ import annotations

from dataclasses import replace

import pytest

from plan_engine.models import (
    AdjacencyRule,
    AreaConstraint,
    CoreSpec,
    EmbeddedClosetSpec,
    EnvelopeSpec,
    FloorSpec,
    GridSpec,
    PlanSpec,
    ShapeSpec,
    SiteSpec,
    SizeConstraints,
    SpaceSpec,
    TopologySpec,
    ValidationReport,
)
from plan_engine.solver import PlanSolver
from plan_engine.validator.connectivity import validate_connectivity


def _closet_wic_spec() -> PlanSpec:
    return PlanSpec(
        version="0.2",
        units="mm",
        grid=GridSpec(minor=455, major=910),
        site=SiteSpec(
            envelope=EnvelopeSpec(type="rectangle", width=7280, depth=5460),
            north="top",
        ),
        floors={
            "F1": FloorSpec(
                id="F1",
                core=CoreSpec(stair=None),
                spaces=[
                    SpaceSpec(
                        id="entry",
                        type="entry",
                        area=AreaConstraint(min_tatami=1.8, target_tatami=2.0),
                        size_constraints=SizeConstraints(min_width=910),
                    ),
                    SpaceSpec(
                        id="hall1",
                        type="hall",
                        area=AreaConstraint(min_tatami=2.5, target_tatami=4.0),
                        size_constraints=SizeConstraints(min_width=910),
                        shape=ShapeSpec(allow=["L2"], rect_components_max=3),
                    ),
                    SpaceSpec(
                        id="master",
                        type="master_bedroom",
                        area=AreaConstraint(min_tatami=6.0, target_tatami=7.5),
                        size_constraints=SizeConstraints(min_width=1820),
                    ),
                    SpaceSpec(
                        id="bed2",
                        type="bedroom",
                        area=AreaConstraint(min_tatami=4.5, target_tatami=5.5),
                        size_constraints=SizeConstraints(min_width=1820),
                    ),
                    SpaceSpec(
                        id="wic_master",
                        type="wic",
                        parent_id="master",
                        area=AreaConstraint(min_tatami=1.8, target_tatami=2.2),
                        size_constraints=SizeConstraints(min_width=910),
                    ),
                ],
                embedded_closets=[
                    EmbeddedClosetSpec(
                        id="closet_bed2",
                        parent_id="bed2",
                        area=AreaConstraint(min_tatami=1.0, target_tatami=1.2),
                        depth_mm=910,
                    )
                ],
                topology=TopologySpec(
                    adjacency=[
                        AdjacencyRule("entry", "hall1", "required"),
                        AdjacencyRule("hall1", "master", "required"),
                        AdjacencyRule("hall1", "bed2", "required"),
                        AdjacencyRule("hall1", "wic_master", "required"),
                        AdjacencyRule("master", "wic_master", "required"),
                    ]
                ),
            )
        },
    )


def test_solver_preserves_parent_id_and_grid_alignment_for_closets() -> None:
    spec = _closet_wic_spec()

    solution = PlanSolver(max_time_seconds=15.0, num_workers=2).solve(spec)
    floor = solution.floors["F1"]

    assert floor.spaces["wic_master"].parent_id == "master"
    closet = next(item for item in floor.embedded_closets if item.id == "closet_bed2")
    assert closet.parent_id == "bed2"

    for space_id in ("wic_master",):
        for rect in floor.spaces[space_id].rects:
            assert rect.x % spec.grid.minor == 0
            assert rect.y % spec.grid.minor == 0
            assert rect.w % spec.grid.minor == 0
            assert rect.h % spec.grid.minor == 0
    assert closet.rect.x % spec.grid.minor == 0
    assert closet.rect.y % spec.grid.minor == 0
    assert closet.rect.w % spec.grid.minor == 0
    assert closet.rect.h % spec.grid.minor == 0

    wic_rect = floor.spaces["wic_master"].rects[0]
    assert min(wic_rect.w, wic_rect.h) >= 1820


def test_solver_rejects_wic_with_non_bedroom_parent() -> None:
    spec = _closet_wic_spec()
    bad_spaces = []
    for space in spec.floors["F1"].spaces:
        if space.id == "wic_master":
            bad_spaces.append(replace(space, parent_id="hall1"))
        else:
            bad_spaces.append(space)
    bad_floor = replace(spec.floors["F1"], spaces=bad_spaces)
    bad_spec = replace(spec, floors={"F1": bad_floor})

    with pytest.raises(ValueError, match="must be bedroom/master_bedroom"):
        PlanSolver(max_time_seconds=15.0, num_workers=2).solve(bad_spec)


def test_solver_closet_wic_layout_has_no_bedroom_pass_through() -> None:
    spec = _closet_wic_spec()
    solution = PlanSolver(max_time_seconds=15.0, num_workers=2).solve(spec)

    report = ValidationReport()
    validate_connectivity(solution, report)

    assert not any("reachable only through bedroom transit" in item for item in report.errors)
