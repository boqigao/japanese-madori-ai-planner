from __future__ import annotations

from plan_engine.models import PlanSolution, Rect, WallSegment
from plan_engine.structural.walls import (
    _balance_ratio,
    _classify_wall_role,
    _merge_intervals,
    _overlap_with_intervals,
    _quadrant_bearing_lengths,
    build_structure_report,
    extract_solution_walls,
)


def test_extract_solution_walls_and_structure_report(solved_solution: PlanSolution) -> None:
    walls = extract_solution_walls(solved_solution)
    assert walls
    assert set(walls).issuperset(solved_solution.floors.keys())

    report = build_structure_report(solved_solution, walls)
    assert report.floor_metrics
    assert report.assumptions
    assert report.continuity_metrics


def test_low_level_structural_helpers() -> None:
    assert _merge_intervals([(0, 10), (10, 20), (30, 40)]) == [(0, 20), (30, 40)]
    assert _overlap_with_intervals(5, 15, [(0, 10), (12, 20)]) == 8

    role_exterior = _classify_wall_role(kind="exterior", line_coord=0, span_length=910, major_grid=910)
    role_bearing = _classify_wall_role(kind="interior", line_coord=910, span_length=910, major_grid=910)
    role_partition = _classify_wall_role(kind="interior", line_coord=455, span_length=455, major_grid=910)
    assert role_exterior == "load_bearing"
    assert role_bearing == "candidate_bearing"
    assert role_partition == "partition"

    walls = [
        WallSegment(
            id="w1",
            floor_id="F1",
            orientation="vertical",
            line_coord_mm=455,
            span_start_mm=0,
            span_end_mm=910,
            role="load_bearing",
            kind="exterior",
        ),
        WallSegment(
            id="w2",
            floor_id="F1",
            orientation="horizontal",
            line_coord_mm=455,
            span_start_mm=0,
            span_end_mm=910,
            role="candidate_bearing",
            kind="interior",
        ),
    ]
    quadrants = _quadrant_bearing_lengths(walls, width=1820, depth=1820)
    assert len(quadrants) == 4
    assert _balance_ratio(quadrants) is not None
    assert _balance_ratio((0, 0, 0, 0)) is None


def test_solution_json_contains_structure_report(solved_solution: PlanSolution) -> None:
    payload = solved_solution.to_dict()
    assert "structure_report" in payload
    assert "walls" in payload
    assert payload["structure_report"]["assumptions"]

    # Smoke-check one wall payload schema.
    first_floor = next(iter(payload["walls"].values()))
    first_wall = first_floor[0]
    assert {"id", "floor_id", "orientation", "line_coord_mm", "span_mm"}.issubset(first_wall)


def test_rect_area_basic() -> None:
    rect = Rect(0, 0, 455, 910)
    assert rect.area == 455 * 910
