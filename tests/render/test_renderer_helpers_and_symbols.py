from __future__ import annotations

import svgwrite
import pytest

from plan_engine.models import FloorSolution, Rect, SpaceGeometry
from plan_engine.renderer.core import SvgRenderer
from plan_engine.renderer.dimensions import (
    _normalize_breakpoints,
    _side_axis,
    _snap_to_minor,
    draw_dimension_line,
)
from plan_engine.renderer.helpers import (
    _display_space_name,
    _edge_shared_segment,
    _portal_for_floor,
    _portal_hall_opening_segment,
    _space_boundary_segments,
    _stair_label_point,
)
from plan_engine.renderer.stair import draw_stair_steps
from plan_engine.renderer.symbols import draw_door_symbol, draw_window_symbol


def _empty_drawing() -> svgwrite.Drawing:
    return svgwrite.Drawing(size=("400px", "300px"), profile="tiny")


def test_display_space_name_en_and_ja(monkeypatch) -> None:
    monkeypatch.setenv("PLAN_ENGINE_LABEL_LANG", "en")
    assert _display_space_name("bed2", "bedroom") == "Bedroom 2"
    assert _display_space_name("auto_fill_1", "storage") == "Storage"

    monkeypatch.setenv("PLAN_ENGINE_LABEL_LANG", "ja")
    assert _display_space_name("bed2", "bedroom").startswith("洋室")


def test_space_boundary_segments_removes_internal_edges() -> None:
    # Two adjacent cells should be merged into one outer rectangle boundary.
    rects = [Rect(0, 0, 455, 455), Rect(455, 0, 455, 455)]
    segments = _space_boundary_segments(rects)
    assert ((0, 0), (910, 0)) in segments
    assert ((0, 455), (910, 455)) in segments
    # Internal seam (x=455) should not appear as boundary.
    assert ((455, 0), (455, 455)) not in segments


def test_portal_related_helpers() -> None:
    portal = Rect(910, 0, 910, 910)
    hall = Rect(0, 0, 910, 910)

    seg = _edge_shared_segment(portal, hall, "left")
    assert seg == ((910, 0), (910, 910))
    assert _edge_shared_segment(portal, hall, "right") is None
    assert _edge_shared_segment(portal, hall, "diag") is None

    longest = _portal_hall_opening_segment(portal, [hall], "left")
    assert longest == ((910, 0), (910, 910))

    components = [Rect(0, 0, 910, 910), Rect(910, 0, 910, 910)]
    x, y = _stair_label_point(components, portal_component_index=3)
    assert x > 0 and y > 0


def test_portal_for_floor_requires_stair() -> None:
    floor = FloorSolution(
        id="F1",
        spaces={"hall1": SpaceGeometry("hall1", "hall", [Rect(0, 0, 910, 910)])},
        stair=None,
        topology=[],
    )
    with pytest.raises(ValueError, match="without stair geometry"):
        _portal_for_floor(floor, floor_index=0, total_floors=1)


def test_symbol_drawing_vertical_and_horizontal() -> None:
    drawing = _empty_drawing()
    x_fn = lambda mm: float(mm) / 10.0
    y_fn = lambda mm: float(mm) / 10.0

    door_seg_v = draw_door_symbol(
        drawing=drawing,
        p1=(0, 0),
        p2=(0, 1820),
        exterior=True,
        boundary=Rect(0, 0, 3640, 3640),
        reverse_swing=False,
        draw_arc=True,
        force_arc_small=True,
        x_fn=x_fn,
        y_fn=y_fn,
        scale=0.1,
    )
    door_seg_h = draw_door_symbol(
        drawing=drawing,
        p1=(0, 0),
        p2=(1820, 0),
        exterior=False,
        boundary=None,
        reverse_swing=True,
        draw_arc=False,
        force_arc_small=False,
        x_fn=x_fn,
        y_fn=y_fn,
        scale=0.1,
    )
    win_seg_v = draw_window_symbol(drawing, (0, 0), (0, 1820), 0.5, x_fn=x_fn, y_fn=y_fn)
    win_seg_h = draw_window_symbol(drawing, (0, 0), (1820, 0), 0.5, x_fn=x_fn, y_fn=y_fn)

    assert door_seg_v[0][0] == door_seg_v[1][0]
    assert door_seg_h[0][1] == door_seg_h[1][1]
    assert win_seg_v[0][0] == win_seg_v[1][0]
    assert win_seg_h[0][1] == win_seg_h[1][1]


def test_dimension_helpers_and_draw_dimension_line() -> None:
    renderer = SvgRenderer(scale=0.1, margin_px=20)
    drawing = _empty_drawing()

    draw_dimension_line(renderer, drawing, (0, 0), (910, 0), offset_px=12, label="910", vertical=False)
    draw_dimension_line(renderer, drawing, (0, 0), (0, 910), offset_px=12, label="910", vertical=True)

    assert _side_axis(Rect(0, 0, 910, 1820), "top") == (0, 910, 0)
    assert _snap_to_minor(500) == 455
    assert _normalize_breakpoints({0, 460, 910}, 0, 910) == [0, 455, 910]
    with pytest.raises(ValueError, match="unsupported side"):
        _side_axis(Rect(0, 0, 910, 1820), "diag")


def test_draw_stair_steps_smoke() -> None:
    renderer = SvgRenderer(scale=0.1, margin_px=20)
    drawing = _empty_drawing()
    draw_stair_steps(renderer, drawing, "straight", tread_count=8, components=[Rect(0, 0, 910, 1820)])
    draw_stair_steps(
        renderer,
        drawing,
        "L_landing",
        tread_count=10,
        components=[Rect(0, 0, 910, 910), Rect(910, 0, 910, 910), Rect(910, 910, 910, 910)],
    )
    draw_stair_steps(
        renderer,
        drawing,
        "U_turn",
        tread_count=10,
        components=[Rect(0, 910, 910, 1365), Rect(0, 0, 1820, 910), Rect(910, 910, 910, 1365)],
    )
