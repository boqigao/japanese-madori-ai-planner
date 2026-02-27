from __future__ import annotations

import json
from pathlib import Path

from plan_engine.io import write_report, write_solution_json
from plan_engine.renderer import SvgRenderer


def test_end_to_end_solution_is_valid(sample_spec, solved_solution, solved_report) -> None:
    assert solved_solution.units == "mm"
    assert set(solved_solution.floors) == set(sample_spec.floors)
    assert solved_solution.structure_report is not None
    assert solved_solution.walls
    assert solved_report.is_valid


def test_renderer_writes_svg_and_png(tmp_path: Path, solved_solution, monkeypatch) -> None:
    monkeypatch.setenv("PLAN_ENGINE_DRAW_STRUCTURAL_WALLS", "1")
    renderer = SvgRenderer(scale=0.10)
    written = renderer.render(solved_solution, tmp_path)

    assert written
    for floor_id in solved_solution.floors:
        assert (tmp_path / f"{floor_id}.svg").exists()
        assert (tmp_path / f"{floor_id}.png").exists()


def test_io_writes_solution_and_report(tmp_path: Path, solved_solution, solved_report) -> None:
    solution_path = write_solution_json(solved_solution, tmp_path / "solution.json")
    report_path = write_report(solved_report, tmp_path / "report.txt")

    payload = json.loads(solution_path.read_text(encoding="utf-8"))
    report_text = report_path.read_text(encoding="utf-8")

    assert "floors" in payload
    assert "walls" in payload
    assert "structure_report" in payload
    assert report_text.startswith("valid=")
    assert "Structural:" in report_text
