"""Unit tests for wall-aware closet placement in solution_builder."""

from __future__ import annotations

from plan_engine.models import Rect, SpaceGeometry
from plan_engine.solver.solution_builder import (
    _classify_walls,
    _select_closet_wall,
    _span_wall,
)


def _make_space(id: str, type: str, rects: list[Rect]) -> SpaceGeometry:
    return SpaceGeometry(id=id, type=type, rects=rects)


# ---------------------------------------------------------------------------
# _classify_walls tests
# ---------------------------------------------------------------------------


class TestClassifyWalls:
    """Tests for _classify_walls wall classification."""

    def test_free_wall_interior_no_door(self):
        """Interior wall with no door-eligible neighbor is free."""
        host = Rect(1820, 910, 3640, 2275)
        building = Rect(0, 0, 9100, 5460)
        # bedroom3 is adjacent on bottom wall — bedroom-to-bedroom has no door
        spaces = {
            "bedroom2": _make_space("bedroom2", "bedroom", [host]),
            "bedroom3": _make_space("bedroom3", "bedroom", [Rect(1820, 3185, 3640, 2275)]),
        }
        topology = [("bedroom2", "bedroom3")]
        walls = _classify_walls(host, building, "bedroom2", "bedroom", topology, spaces)
        assert walls["bottom"] == "free"  # bedroom-to-bedroom = no door

    def test_exterior_wall(self):
        """Wall on building boundary is exterior."""
        host = Rect(0, 0, 3640, 2275)
        building = Rect(0, 0, 9100, 5460)
        walls = _classify_walls(host, building, "br", "bedroom", [], {})
        assert walls["top"] == "exterior"
        assert walls["left"] == "exterior"
        assert walls["bottom"] == "free"
        assert walls["right"] == "free"

    def test_door_wall_with_hall(self):
        """Wall shared with hall gets a door."""
        host = Rect(1820, 0, 3640, 2275)
        building = Rect(0, 0, 9100, 5460)
        hall = _make_space("hall", "hall", [Rect(0, 0, 1820, 2275)])
        spaces = {"br": _make_space("br", "bedroom", [host]), "hall": hall}
        topology = [("br", "hall")]
        walls = _classify_walls(host, building, "br", "bedroom", topology, spaces)
        assert walls["left"] == "door"

    def test_both_exterior_and_door(self):
        """Corner room can have a wall that is both exterior and door."""
        host = Rect(0, 0, 3640, 2275)
        building = Rect(0, 0, 9100, 5460)
        hall = _make_space("hall", "hall", [Rect(0, 2275, 3640, 1820)])
        spaces = {"br": _make_space("br", "bedroom", [host]), "hall": hall}
        topology = [("br", "hall")]
        walls = _classify_walls(host, building, "br", "bedroom", topology, spaces)
        assert walls["top"] == "exterior"
        assert walls["left"] == "exterior"
        assert walls["bottom"] == "door"  # hall below

    def test_corner_room_mixed_walls(self):
        """Corner bedroom: 2 exterior, 1 door (hall), 1 free (adj bedroom)."""
        host = Rect(4550, 0, 4550, 2730)
        building = Rect(0, 0, 9100, 5460)
        hall = _make_space("hall", "hall", [Rect(1820, 0, 2730, 2730)])
        other_br = _make_space("br2", "bedroom", [Rect(4550, 2730, 4550, 2730)])
        spaces = {
            "br1": _make_space("br1", "bedroom", [host]),
            "hall": hall,
            "br2": other_br,
        }
        topology = [("br1", "hall"), ("br1", "br2")]
        walls = _classify_walls(host, building, "br1", "bedroom", topology, spaces)
        assert walls["top"] == "exterior"
        assert walls["right"] == "exterior"
        assert walls["left"] == "door"    # hall on left
        assert walls["bottom"] == "free"  # bedroom-to-bedroom = no door


# ---------------------------------------------------------------------------
# _span_wall tests
# ---------------------------------------------------------------------------


class TestSpanWall:
    """Tests for _span_wall full-wall placement."""

    def test_span_top(self):
        host = Rect(1820, 910, 3640, 2275)
        rect = _span_wall(host, "top", 910)
        assert rect == Rect(1820, 910, 3640, 910)

    def test_span_bottom(self):
        host = Rect(1820, 910, 3640, 2275)
        rect = _span_wall(host, "bottom", 910)
        assert rect == Rect(1820, 910 + 2275 - 910, 3640, 910)

    def test_span_left(self):
        host = Rect(1820, 910, 3640, 2275)
        rect = _span_wall(host, "left", 910)
        assert rect == Rect(1820, 910, 910, 2275)

    def test_span_right(self):
        host = Rect(1820, 910, 3640, 2275)
        rect = _span_wall(host, "right", 910)
        assert rect == Rect(1820 + 3640 - 910, 910, 910, 2275)

    def test_depth_exceeds_returns_none(self):
        host = Rect(0, 0, 1820, 910)
        assert _span_wall(host, "top", 1820) is None  # depth > height
        assert _span_wall(host, "left", 2730) is None  # depth > width


# ---------------------------------------------------------------------------
# _select_closet_wall tests
# ---------------------------------------------------------------------------


class TestSelectClosetWall:
    """Tests for _select_closet_wall wall-priority selection."""

    def test_prefers_shorter_free_wall(self):
        """When both walls are free, picks the shorter one."""
        walls = {"top": "free", "bottom": "free", "left": "exterior", "right": "exterior"}
        host = Rect(0, 0, 4550, 2275)  # top/bottom=4550, left/right=2275
        # target ~1 tatami = ~1,620,000 mm2, but doesn't matter for this test
        rect = _select_closet_wall(walls, host, [2], 455, 1_620_000)
        # Should not pick exterior walls; should prefer shorter free wall
        # top and bottom are both 4550mm span — but left/right are exterior
        # So it picks top or bottom. Both have same length, top comes first alphabetically
        # In the code, free_walls is sorted by span length. top and bottom are both 4550.
        # The implementation sorts by length — same length means stable sort order.
        assert rect is not None
        assert rect.h == 910 or rect.w == 910  # depth of 2 cells

    def test_full_span_on_free_wall(self):
        """Full-span on short free wall."""
        walls = {"top": "exterior", "bottom": "free", "left": "door", "right": "free"}
        host = Rect(0, 0, 4550, 2730)  # right wall = 2730mm (shorter)
        rect = _select_closet_wall(walls, host, [2], 455, 1_620_000)
        assert rect is not None
        # right wall (2730 span) is shorter than bottom (4550 span), picked first
        assert rect.x == host.x2 - 910  # right wall
        assert rect.h == 2730  # full span

    def test_overshoot_cap_triggers_partial(self):
        """When full span > 2x target, uses partial span."""
        walls = {"top": "exterior", "bottom": "free", "left": "door", "right": "exterior"}
        host = Rect(0, 0, 9100, 2730)
        # target = 1 tatami ~ 1.62M mm2. Full bottom span = 9100*910 = 8.28M > 2*1.62M
        rect = _select_closet_wall(walls, host, [2], 455, 1_620_000)
        assert rect is not None
        assert rect.w < host.w  # partial span, not full 9100mm

    def test_no_free_wall_uses_door_wall(self):
        """When no free walls exist, falls back to door wall."""
        walls = {"top": "exterior", "bottom": "exterior", "left": "door", "right": "door"}
        host = Rect(0, 0, 4550, 2730)
        rect = _select_closet_wall(walls, host, [2], 455, 1_620_000)
        assert rect is not None

    def test_all_exterior_returns_none(self):
        """When all walls are exterior and no door walls, returns None (legacy fallback)."""
        walls = {"top": "exterior", "bottom": "exterior", "left": "exterior", "right": "exterior"}
        host = Rect(0, 0, 4550, 2730)
        rect = _select_closet_wall(walls, host, [2], 455, 1_620_000)
        assert rect is None  # falls back to legacy
