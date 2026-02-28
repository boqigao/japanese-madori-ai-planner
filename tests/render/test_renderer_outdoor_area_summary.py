from __future__ import annotations

import svgwrite

from plan_engine.models import EnvelopeSpec, FloorSolution, GridSpec, PlanSolution, Rect, SpaceGeometry
from plan_engine.renderer.annotations import draw_floor_area_summary
from plan_engine.renderer.core import _should_draw_interior_door, SvgRenderer


def test_renderer_area_summary_separates_indoor_and_outdoor() -> None:
    renderer = SvgRenderer(scale=0.1, margin_px=20)
    drawing = svgwrite.Drawing(size=("800px", "600px"), profile="tiny")
    solution = PlanSolution(
        units="mm",
        grid=GridSpec(455, 910),
        envelope=EnvelopeSpec(type="rectangle", width=3640, depth=2730),
        north="top",
        floors={
            "F1": FloorSolution(
                id="F1",
                spaces={
                    "storage1": SpaceGeometry("storage1", "storage", [Rect(0, 0, 2730, 2730)], "indoor"),
                    "balcony1": SpaceGeometry("balcony1", "balcony", [Rect(2730, 0, 910, 2730)], "outdoor"),
                },
                stair=None,
                topology=[("storage1", "balcony1")],
                buildable_mask=[Rect(0, 0, 2730, 2730)],
                indoor_buildable_area_mm2=2730 * 2730,
            )
        },
    )
    site_rect = Rect(0, 0, 3640, 2730)

    draw_floor_area_summary(renderer, drawing, solution, "F1", site_rect)
    svg_text = drawing.tostring()

    assert "Total indoor" in svg_text
    assert "Total outdoor" in svg_text


def test_renderer_door_policy_allows_indoor_outdoor_and_blocks_outdoor_outdoor() -> None:
    assert _should_draw_interior_door("hall", "balcony") is True
    assert _should_draw_interior_door("balcony", "veranda") is False
