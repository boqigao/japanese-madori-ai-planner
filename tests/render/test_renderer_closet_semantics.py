from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from plan_engine.models import (
    EmbeddedClosetGeometry,
    EnvelopeSpec,
    FloorSolution,
    GridSpec,
    PlanSolution,
    Rect,
    SpaceGeometry,
)
from plan_engine.renderer.core import (
    SvgRenderer,
    _should_draw_interior_door,
    _subtract_colinear_segment,
)


def test_should_draw_interior_door_suppresses_bedroom_to_bedroom() -> None:
    assert not _should_draw_interior_door("bedroom", "bedroom")
    assert not _should_draw_interior_door("master_bedroom", "bedroom")
    assert not _should_draw_interior_door("closet", "bedroom")
    assert _should_draw_interior_door("hall", "bedroom")


def test_subtract_colinear_segment_splits_overlap() -> None:
    base = ((1820, 0), (1820, 2730))
    cut = ((1820, 0), (1820, 1365))
    assert _subtract_colinear_segment(base, cut) == [((1820, 1365), (1820, 2730))]


def test_renderer_outputs_closet_and_wic_labels(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PLAN_ENGINE_LABEL_LANG", "en")

    solution = PlanSolution(
        units="mm",
        grid=GridSpec(455, 910),
        envelope=EnvelopeSpec(type="rectangle", width=3640, depth=3640),
        north="top",
        floors={
            "F1": FloorSolution(
                id="F1",
                spaces={
                    "entry": SpaceGeometry("entry", "entry", [Rect(0, 2730, 910, 910)]),
                    "hall1": SpaceGeometry("hall1", "hall", [Rect(910, 2730, 910, 910)]),
                    "master": SpaceGeometry("master", "master_bedroom", [Rect(0, 0, 1820, 2730)]),
                    "wic1": SpaceGeometry(
                        "wic1",
                        "wic",
                        [Rect(1820, 1365, 910, 1365)],
                        parent_id="master",
                    ),
                    "storage1": SpaceGeometry("storage1", "storage", [Rect(2730, 0, 910, 2730)]),
                },
                embedded_closets=[
                    EmbeddedClosetGeometry(
                        id="closet1",
                        parent_id="master",
                        rect=Rect(910, 0, 910, 1365),
                    )
                ],
                stair=None,
                topology=[("entry", "hall1"), ("hall1", "master"), ("master", "wic1")],
            )
        },
    )

    outputs = SvgRenderer(scale=0.1, margin_px=20).render(solution, tmp_path)
    svg_path = next(path for path in outputs if path.suffix == ".svg")
    svg_text = svg_path.read_text(encoding="utf-8")

    assert ">CL<" in svg_text
    assert "W.I.C" in svg_text
    assert "Storage 1" in svg_text
    root = ET.fromstring(svg_text)
    ns = {"svg": "http://www.w3.org/2000/svg"}
    thick_lines = root.findall(".//svg:line", ns)
    has_closet_parent_wall = any(
        line.get("stroke") == "#2f2f2f"
        and line.get("stroke-width") == "2.2"
        and line.get("x1") == line.get("x2") == "202.0"
        and line.get("y1") == "20.0"
        and line.get("y2") == "156.5"
        for line in thick_lines
    )
    assert not has_closet_parent_wall
