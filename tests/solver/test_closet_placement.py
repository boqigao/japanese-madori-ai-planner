"""Unit tests for short-wall-span closet placement pipeline."""

from __future__ import annotations

from plan_engine.models import Rect, SpaceGeometry
from plan_engine.solver.solution_builder import (
    _closet_blocked_exterior_segments,
    _pick_closet_wall,
    _place_closet_on_wall,
    _would_block_all_windows,
    compute_door_segments,
)


def _make_space(id: str, type: str, rects: list[Rect]) -> SpaceGeometry:
    return SpaceGeometry(id=id, type=type, rects=rects)


# ---------------------------------------------------------------------------
# compute_door_segments tests
# ---------------------------------------------------------------------------


class TestComputeDoorSegments:
    """Tests for compute_door_segments utility."""

    def test_hall_bedroom_door_found(self):
        """Hall-bedroom adjacency produces a door segment."""
        spaces = {
            "hall": _make_space("hall", "hall", [Rect(3640, 2275, 2730, 910)]),
            "bed2": _make_space("bed2", "bedroom", [Rect(0, 0, 3640, 3185)]),
        }
        topology = [("hall", "bed2")]
        segments = compute_door_segments(spaces, topology)
        key = frozenset(("hall", "bed2"))
        assert key in segments
        seg = segments[key]
        # Shared edge is vertical at x=3640, overlapping y range
        assert seg[0][0] == seg[1][0] == 3640  # vertical segment
        length = abs(seg[1][1] - seg[0][1])
        assert length > 0

    def test_bedroom_bedroom_no_door(self):
        """Bedroom-to-bedroom adjacency produces no door segment."""
        spaces = {
            "bed2": _make_space("bed2", "bedroom", [Rect(0, 0, 3640, 3185)]),
            "bed3": _make_space("bed3", "bedroom", [Rect(3640, 0, 3640, 3185)]),
        }
        topology = [("bed2", "bed3")]
        segments = compute_door_segments(spaces, topology)
        assert frozenset(("bed2", "bed3")) not in segments

    def test_l_shaped_hall_picks_longest_segment(self):
        """Hall with multiple rects picks the longest shared segment with bedroom."""
        hall_rects = [
            Rect(0, 0, 910, 1820),   # left portion
            Rect(910, 0, 910, 910),   # middle portion
            Rect(1820, 0, 910, 1820), # right portion — shares edge with bedroom
        ]
        bed_rect = Rect(2730, 0, 2730, 1820)
        spaces = {
            "hall": _make_space("hall", "hall", hall_rects),
            "bed1": _make_space("bed1", "bedroom", [bed_rect]),
        }
        topology = [("hall", "bed1")]
        segments = compute_door_segments(spaces, topology)
        key = frozenset(("hall", "bed1"))
        assert key in segments
        seg = segments[key]
        # The right hall rect (1820,0,910,1820) shares x=2730 with bed (2730,0,...)
        # Shared y range: max(0,0)=0, min(1820,1820)=1820 → length 1820
        assert seg[0][0] == seg[1][0] == 2730
        length = abs(seg[1][1] - seg[0][1])
        assert length == 1820

    def test_missing_space_skipped(self):
        """Topology pair with missing space is skipped gracefully."""
        spaces = {
            "hall": _make_space("hall", "hall", [Rect(0, 0, 910, 910)]),
        }
        topology = [("hall", "bed1")]
        segments = compute_door_segments(spaces, topology)
        assert len(segments) == 0

    def test_no_shared_edge_produces_no_segment(self):
        """Topology pair with no actual shared edge produces no segment."""
        spaces = {
            "hall": _make_space("hall", "hall", [Rect(0, 0, 910, 910)]),
            "bed1": _make_space("bed1", "bedroom", [Rect(2000, 2000, 910, 910)]),
        }
        topology = [("hall", "bed1")]
        segments = compute_door_segments(spaces, topology)
        assert len(segments) == 0


# ---------------------------------------------------------------------------
# _pick_closet_wall tests
# ---------------------------------------------------------------------------


class TestPickClosetWall:
    """Tests for _pick_closet_wall short-wall-span selection."""

    def test_horizontal_room_picks_left_or_right(self):
        """Horizontal room (W > H) candidates are left/right (ends of long axis)."""
        # Room at interior position: left wall = interior, right wall = exterior
        host = Rect(2730, 0, 5460, 2275)
        building = Rect(0, 0, 8190, 5460)
        door_segs: dict[frozenset[str], tuple[tuple[int, int], tuple[int, int]]] = {}
        wall, is_fallback = _pick_closet_wall(host, building, door_segs, "bed1", [])
        assert wall in ("left", "right")
        # Left wall (x=2730) is interior, right wall (x2=8190) is exterior → picks left
        assert wall == "left"
        assert is_fallback is False

    def test_vertical_room_picks_top_or_bottom(self):
        """Vertical room (H > W) candidates are top/bottom (ends of long axis)."""
        host = Rect(6370, 0, 2730, 5460)
        building = Rect(0, 0, 9100, 5460)
        # top (y=0) is exterior, bottom (y2=5460) is exterior
        # left (x=6370) is interior — but left/right are not candidates for vertical room
        door_segs: dict[frozenset[str], tuple[tuple[int, int], tuple[int, int]]] = {}
        wall, is_fallback = _pick_closet_wall(host, building, door_segs, "bed3", [])
        assert wall in ("top", "bottom")
        assert is_fallback is False

    def test_prefers_interior_over_exterior(self):
        """Interior wall is preferred over exterior."""
        # Horizontal room: left is interior, right is on building boundary
        host = Rect(1820, 0, 3640, 2275)
        building = Rect(0, 0, 5460, 5460)
        door_segs: dict[frozenset[str], tuple[tuple[int, int], tuple[int, int]]] = {}
        wall, _ = _pick_closet_wall(host, building, door_segs, "bed1", [])
        # left (x=1820) is interior, right (x2=5460) is exterior → picks left
        assert wall == "left"

    def test_near_square_room_fallback(self):
        """Perfect square considers all four walls."""
        host = Rect(0, 0, 2730, 2730)
        building = Rect(0, 0, 9100, 5460)
        # top (y=0) exterior, left (x=0) exterior, bottom & right are interior
        door_segs: dict[frozenset[str], tuple[tuple[int, int], tuple[int, int]]] = {}
        wall, _ = _pick_closet_wall(host, building, door_segs, "bed1", [])
        assert wall in ("bottom", "right")  # interior walls

    def test_door_segment_tiebreaker(self):
        """When both candidates are interior, prefer the wall without a door."""
        host = Rect(1820, 1820, 3640, 2275)
        building = Rect(0, 0, 9100, 5460)
        # Both left and right are interior. Put a door on the left wall.
        door_segs = {
            frozenset(("bed1", "hall")): ((1820, 1820), (1820, 4095)),  # left wall
        }
        wall, _ = _pick_closet_wall(host, building, door_segs, "bed1", [("bed1", "hall")])
        # left has a door, right has no door → picks right
        assert wall == "right"

    def test_prefers_exterior_no_door_over_interior_with_door(self):
        """Exterior wall without door is preferred over interior wall with door.

        CL spans the full short side. If placed on the door wall, it would
        completely block the door. Better to lose a window than lose a door.
        """
        # Horizontal room: left is exterior, right is interior (hall side with door)
        host = Rect(0, 0, 4095, 2730)
        building = Rect(0, 0, 10920, 5460)
        door_segs = {
            frozenset(("bed2", "hall")): ((4095, 0), (4095, 2730)),  # right wall = door
        }
        wall, _ = _pick_closet_wall(host, building, door_segs, "bed2", [("bed2", "hall")])
        # right has door (interior), left has no door (exterior) → picks left (exterior)
        assert wall == "left"

    def test_avoids_wall_that_blocks_perpendicular_door(self):
        """CL on top wall would block a door on the right (perpendicular) wall.

        Vertical room: candidates are top/bottom. Door is on the right wall
        near the top corner. CL strip on 'top' spans the full width and its
        right edge touches x=host.x2 where the door is → door blocked.
        Picks 'bottom' instead even though 'top' is interior.
        """
        host = Rect(0, 2730, 2275, 5460)
        building = Rect(0, 0, 8190, 8190)
        # Door on right wall at top portion: x=2275, y=[2730, 3640]
        door_segs = {
            frozenset(("bed4", "hall2")): ((2275, 2730), (2275, 3640)),
        }
        wall, _ = _pick_closet_wall(host, building, door_segs, "bed4", [("hall2", "bed4")])
        # top is interior but blocks door; bottom is exterior but safe
        assert wall == "bottom"


# ---------------------------------------------------------------------------
# _place_closet_on_wall tests
# ---------------------------------------------------------------------------


class TestPlaceClosetOnWall:
    """Tests for _place_closet_on_wall rect construction."""

    def test_top_wall(self):
        host = Rect(0, 0, 5460, 2275)
        rect = _place_closet_on_wall(host, "top", 910, 5460)
        assert rect == Rect(0, 0, 5460, 910)

    def test_bottom_wall(self):
        host = Rect(0, 0, 5460, 2275)
        rect = _place_closet_on_wall(host, "bottom", 910, 5460)
        assert rect == Rect(0, 2275 - 910, 5460, 910)

    def test_left_wall(self):
        host = Rect(1820, 0, 3640, 2275)
        rect = _place_closet_on_wall(host, "left", 910, 2275)
        assert rect == Rect(1820, 0, 910, 2275)

    def test_right_wall(self):
        host = Rect(1820, 0, 3640, 2275)
        rect = _place_closet_on_wall(host, "right", 910, 2275)
        assert rect == Rect(1820 + 3640 - 910, 0, 910, 2275)


# ---------------------------------------------------------------------------
# _closet_blocked_exterior_segments tests
# ---------------------------------------------------------------------------


class TestClosetBlockedExteriorSegments:
    """Tests for _closet_blocked_exterior_segments helper."""

    def test_interior_closet_returns_empty(self):
        """CL on interior wall returns no blocked exterior segments."""
        building = Rect(0, 0, 9100, 5460)
        closet = Rect(4550, 1820, 910, 2275)  # interior, not touching any building edge
        assert _closet_blocked_exterior_segments(closet, building) == []

    def test_exterior_closet_returns_matching_edge(self):
        """CL on exterior wall returns the matching edge segment."""
        building = Rect(0, 0, 9100, 5460)
        closet = Rect(6370, 0, 2730, 910)  # top edge at y=0 is on building boundary
        segments = _closet_blocked_exterior_segments(closet, building)
        assert ((6370, 0), (9100, 0)) in segments
        # Also right edge at x=9100 is on boundary
        assert ((9100, 0), (9100, 910)) in segments

    def test_corner_closet_covers_two_edges(self):
        """CL in corner covers two exterior edges."""
        building = Rect(0, 0, 9100, 5460)
        closet = Rect(0, 0, 910, 2275)  # top-left corner
        segments = _closet_blocked_exterior_segments(closet, building)
        assert ((0, 0), (910, 0)) in segments   # top edge
        assert ((0, 0), (0, 2275)) in segments   # left edge
        assert len(segments) == 2


# ---------------------------------------------------------------------------
# _would_block_all_windows tests
# ---------------------------------------------------------------------------


class TestWouldBlockAllWindows:
    """Tests for _would_block_all_windows helper."""

    def test_single_exterior_wall_returns_true(self):
        """Room with only one exterior wall: blocking it kills all windows."""
        # Room touches only left boundary (x=0)
        host = Rect(0, 3640, 4550, 3640)
        building = Rect(0, 0, 6370, 12740)
        assert _would_block_all_windows(host, "left", building) is True

    def test_two_exterior_walls_returns_false(self):
        """Room with two exterior walls: blocking one still leaves the other."""
        # Room touches left (x=0) and bottom (y2=12740)
        host = Rect(0, 7280, 3640, 5460)
        building = Rect(0, 0, 6370, 12740)
        assert _would_block_all_windows(host, "left", building) is False
        assert _would_block_all_windows(host, "bottom", building) is False

    def test_corner_room_three_exterior_walls(self):
        """Corner room with three exterior walls: blocking any one is fine."""
        # Room touches top (y=0), left (x=0), right (x2=6370)
        host = Rect(0, 0, 6370, 2730)
        building = Rect(0, 0, 6370, 12740)
        assert _would_block_all_windows(host, "top", building) is False
        assert _would_block_all_windows(host, "left", building) is False

    def test_fully_interior_room(self):
        """Fully interior room: blocking any wall kills all windows (vacuously none)."""
        host = Rect(1820, 1820, 2730, 2730)
        building = Rect(0, 0, 9100, 9100)
        # No exterior walls at all → blocking any wall "kills all" (there are none)
        assert _would_block_all_windows(host, "left", building) is True


# ---------------------------------------------------------------------------
# Window-preserving fallback tests
# ---------------------------------------------------------------------------


class TestWindowPreservingFallback:
    """Tests for closet placement falling back to long-side walls to preserve windows."""

    def test_fallback_to_long_side_when_short_kills_windows(self):
        """Bedroom with one exterior short wall: CL falls back to long-side interior."""
        # Bedroom 4 scenario: only left wall (x=0) is exterior, door on right
        host = Rect(0, 3640, 4550, 3640)
        building = Rect(0, 0, 6370, 12740)
        door_segs = {
            frozenset(("bed4", "hall2")): ((4550, 3640), (4550, 7280)),
        }
        wall, is_fallback = _pick_closet_wall(host, building, door_segs, "bed4", [("hall2", "bed4")])
        # Short-side candidates (left, right) both block all windows or have door
        # Fallback to long-side: top (y=3640, interior) or bottom (y=7280, check)
        assert is_fallback is True
        assert wall in ("top", "bottom")

    def test_no_fallback_when_short_side_preserves_windows(self):
        """Bedroom with two exterior walls: short side works fine, no fallback."""
        # Room touches left (x=0) and bottom (y2=12740)
        host = Rect(0, 7280, 3640, 5460)
        building = Rect(0, 0, 6370, 12740)
        door_segs: dict[frozenset[str], tuple[tuple[int, int], tuple[int, int]]] = {}
        wall, is_fallback = _pick_closet_wall(host, building, door_segs, "master", [])
        assert is_fallback is False
        # Short sides are top/bottom (h > w), both exterior
        # Prefers interior but both are exterior, so picks either
        assert wall in ("top", "bottom")

    def test_partial_span_on_long_wall(self):
        """Fallback placement uses partial span, not full wall length."""
        host = Rect(0, 3640, 4550, 3640)
        # CL target = 1.0 tatami ≈ 1,620,000 mm2, depth = 910mm
        # span = ceil(1620000 / 910) = 1782mm → ceil to 455 grid = 1820mm
        rect = _place_closet_on_wall(host, "top", 910, 1820)
        assert rect.w == 1820
        assert rect.h == 910
        # Anchored at host origin corner
        assert rect.x == host.x
        assert rect.y == host.y

    def test_regression_bed4_narrow_lot_preserves_window(self):
        """Regression: bed4 on 6370×12740 lot with single exterior wall gets windows.

        Original bug: bed4 at (0, 3640, 4550, 3640) had only the left wall
        (x=0) as exterior. CL was placed on the left wall (short side), blocking
        all windows. After fix, CL falls back to a long-side interior wall.
        """
        from plan_engine.solver.solution_builder import _fit_closet_strip

        host = Rect(0, 3640, 4550, 3640)
        building = Rect(0, 0, 6370, 12740)
        # Door on right wall from hall2
        door_segs = {
            frozenset(("bed4", "hall2")): ((4550, 3640), (4550, 7280)),
        }
        target_area_mm2 = 1_620_000  # 1.0 tatami
        cl = _fit_closet_strip(
            host=host,
            target_area_mm2=target_area_mm2,
            depth_cells_candidates=[2],
            minor_grid=455,
            building_rect=building,
            floor_topology=[("hall2", "bed4")],
            solved_spaces={},
            host_id="bed4",
            host_type="bedroom",
            door_segments=door_segs,
        )
        # CL must NOT cover the entire left exterior wall
        left_exterior_blocked = cl.x == 0 and cl.y <= host.y and cl.y2 >= host.y2
        assert not left_exterior_blocked, (
            f"CL {cl} covers entire left exterior wall of bed4 — no windows"
        )
        # CL should be on a long-side (top or bottom) wall, partial span
        is_on_top = cl.y == host.y and cl.h < host.h
        is_on_bottom = cl.y2 == host.y2 and cl.h < host.h
        assert is_on_top or is_on_bottom, f"CL {cl} should be on top/bottom long side"
        # CL width should be partial (< full wall width 4550)
        assert cl.w < host.w, f"CL width {cl.w} should be less than wall {host.w}"
