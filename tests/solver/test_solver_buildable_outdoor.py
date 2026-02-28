from __future__ import annotations

from pathlib import Path

from plan_engine.dsl import load_plan_spec
from plan_engine.solver import PlanSolver


def _fixture_path(name: str) -> Path:
    return Path(__file__).resolve().parents[2] / "resources" / "specs" / name


def test_solver_constrains_indoor_to_buildable_and_places_balcony_outside() -> None:
    spec = load_plan_spec(_fixture_path("buildable_balcony_valid.yaml"))

    solution = PlanSolver(max_time_seconds=10.0, num_workers=2).solve(spec)

    floor = solution.floors["F1"]
    buildable = floor.buildable_mask[0]

    for space_id, space in floor.spaces.items():
        if space.space_class != "indoor":
            continue
        for rect in space.rects:
            assert rect.x >= buildable.x
            assert rect.y >= buildable.y
            assert rect.x2 <= buildable.x2
            assert rect.y2 <= buildable.y2

    balcony = floor.spaces["balcony1"]
    assert balcony.space_class == "outdoor"
    assert all(rect.x >= buildable.x2 for rect in balcony.rects)

    indoor_area = sum(
        rect.area
        for space in floor.spaces.values()
        if space.space_class == "indoor"
        for rect in space.rects
    )
    assert floor.stair is None
    assert indoor_area == floor.indoor_buildable_area_mm2
