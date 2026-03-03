"""Unit tests for Stage 5: topology generation."""

from __future__ import annotations

from plan_engine.generator.distribute import FloorPlan, FloorRoom, _make_fixed_room
from plan_engine.generator.topology import AdjEdge, generate_topology


def _edge_exists(edges: list[AdjEdge], left: str, right: str) -> bool:
    """Check if an edge exists in either direction."""
    return any(
        (e.left == left and e.right == right) or (e.left == right and e.right == left)
        for e in edges
    )


def _edge_strength(edges: list[AdjEdge], left: str, right: str) -> str | None:
    """Get the strength of an edge, or None if not found."""
    for e in edges:
        if (e.left == left and e.right == right) or (e.left == right and e.right == left):
            return e.strength
    return None


class TestStandardF1Topology:
    def test_standard_f1(self):
        """Standard F1: entry, hall, ldk, toilet, washroom, bath, storage, stair."""
        plan = FloorPlan(floor=1, has_stair=True)
        plan.rooms = [
            FloorRoom(id="entry", room_type="entry", floor=1),
            FloorRoom(id="hall1", room_type="hall", floor=1),
            FloorRoom(id="ldk", room_type="ldk", floor=1),
            _make_fixed_room("toilet1", "toilet", 1),
            _make_fixed_room("wash1", "washroom", 1),
            _make_fixed_room("bath1", "bath", 1),
            FloorRoom(id="storage1", room_type="storage", floor=1),
        ]

        edges = generate_topology(plan)

        # Required edges.
        assert _edge_exists(edges, "entry", "hall1")
        assert _edge_exists(edges, "hall1", "stair")
        assert _edge_exists(edges, "hall1", "ldk")
        assert _edge_exists(edges, "hall1", "toilet1")
        assert _edge_exists(edges, "wash1", "bath1")
        assert _edge_exists(edges, "hall1", "wash1")
        assert _edge_exists(edges, "hall1", "storage1")

    def test_no_stair_edge_on_1f(self):
        """1F mode: no stair edge."""
        plan = FloorPlan(floor=1, has_stair=False)
        plan.rooms = [
            FloorRoom(id="entry", room_type="entry", floor=1),
            FloorRoom(id="hall1", room_type="hall", floor=1),
            FloorRoom(id="ldk", room_type="ldk", floor=1),
        ]

        edges = generate_topology(plan)
        assert not _edge_exists(edges, "hall1", "stair")


class TestF2WithCompactWet:
    def test_f2_compact_wet(self):
        """F2 with compact wet and closets."""
        plan = FloorPlan(floor=2, has_stair=True)
        plan.rooms = [
            FloorRoom(id="hall2", room_type="hall", floor=2),
            FloorRoom(id="master", room_type="master_bedroom", floor=2),
            FloorRoom(id="bed2", room_type="bedroom", floor=2),
            FloorRoom(id="bed3", room_type="bedroom", floor=2),
            FloorRoom(id="master_cl", room_type="closet", floor=2, parent_id="master"),
            FloorRoom(id="bed2_cl", room_type="closet", floor=2, parent_id="bed2"),
            FloorRoom(id="bed3_cl", room_type="closet", floor=2, parent_id="bed3"),
            _make_fixed_room("toilet2", "toilet", 2),
            _make_fixed_room("washstand2", "washstand", 2),
            _make_fixed_room("shower2", "shower", 2),
        ]

        edges = generate_topology(plan)

        # Hall connections.
        assert _edge_exists(edges, "hall2", "stair")
        assert _edge_exists(edges, "hall2", "master")
        assert _edge_exists(edges, "hall2", "bed2")
        assert _edge_exists(edges, "hall2", "bed3")
        assert _edge_exists(edges, "hall2", "toilet2")

        # Compact wet adjacency.
        assert _edge_exists(edges, "washstand2", "shower2")

        # Bedroom-closet adjacency.
        assert _edge_exists(edges, "master", "master_cl")
        assert _edge_exists(edges, "bed2", "bed2_cl")
        assert _edge_exists(edges, "bed3", "bed3_cl")


class TestWICPreferred:
    def test_wic_preferred_edge(self):
        """WIC should have preferred (not required) adjacency with master."""
        plan = FloorPlan(floor=2, has_stair=True)
        plan.rooms = [
            FloorRoom(id="hall2", room_type="hall", floor=2),
            FloorRoom(id="master", room_type="master_bedroom", floor=2),
            FloorRoom(id="master_wic", room_type="wic", floor=2, parent_id="master"),
            _make_fixed_room("toilet2", "toilet", 2),
        ]

        edges = generate_topology(plan)

        assert _edge_exists(edges, "master", "master_wic")
        assert _edge_strength(edges, "master", "master_wic") == "preferred"


class TestNoFalseEdges:
    def test_no_edge_for_missing_room(self):
        """No edge generated for room types not present on floor."""
        plan = FloorPlan(floor=2, has_stair=True)
        plan.rooms = [
            FloorRoom(id="hall2", room_type="hall", floor=2),
            FloorRoom(id="master", room_type="master_bedroom", floor=2),
        ]

        edges = generate_topology(plan)

        # No washroom/bath edges since they don't exist.
        assert not _edge_exists(edges, "hall2", "washroom")
        assert not _edge_exists(edges, "hall2", "washstand")
        assert not _edge_exists(edges, "washroom", "bath")
