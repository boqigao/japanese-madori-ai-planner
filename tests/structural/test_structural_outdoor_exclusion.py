from __future__ import annotations

from plan_engine.models import EnvelopeSpec, FloorSolution, GridSpec, PlanSolution, Rect, SpaceGeometry
from plan_engine.structural.walls import extract_solution_walls


def _solution(include_balcony: bool) -> PlanSolution:
    spaces = {
        "storage1": SpaceGeometry("storage1", "storage", [Rect(0, 0, 1820, 1820)], "indoor"),
    }
    if include_balcony:
        spaces["balcony1"] = SpaceGeometry("balcony1", "balcony", [Rect(1820, 0, 1820, 1820)], "outdoor")

    return PlanSolution(
        units="mm",
        grid=GridSpec(455, 910),
        envelope=EnvelopeSpec(type="rectangle", width=3640, depth=1820),
        north="top",
        floors={
            "F1": FloorSolution(
                id="F1",
                spaces=spaces,
                stair=None,
                topology=[],
                buildable_mask=[Rect(0, 0, 1820, 1820)],
                indoor_buildable_area_mm2=1820 * 1820,
            )
        },
    )


def test_structural_wall_extraction_ignores_outdoor_cells() -> None:
    indoor_only = _solution(include_balcony=False)
    with_balcony = _solution(include_balcony=True)

    indoor_walls = extract_solution_walls(indoor_only)["F1"]
    balcony_walls = extract_solution_walls(with_balcony)["F1"]

    assert indoor_walls
    assert len(balcony_walls) == len(indoor_walls)
    assert {(wall.line_coord_mm, wall.span_start_mm, wall.span_end_mm, wall.kind) for wall in balcony_walls} == {
        (wall.line_coord_mm, wall.span_start_mm, wall.span_end_mm, wall.kind) for wall in indoor_walls
    }
