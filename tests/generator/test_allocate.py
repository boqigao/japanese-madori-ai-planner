"""Unit tests for Stage 4: area allocation."""

from __future__ import annotations

from plan_engine.generator.allocate import allocate_floor
from plan_engine.generator.distribute import FloorPlan, FloorRoom, _make_fixed_room
from plan_engine.generator.metrics import compute_metrics
from plan_engine.generator.profiles import ROOM_PROFILE


class TestAllocateFloor:
    def test_normal_8x9_5ldk_f1(self):
        """Normal F1 allocation for 8x9 5LDK — all within bounds."""
        metrics = compute_metrics(8.0, 9.0)
        plan = FloorPlan(floor=1, has_stair=True)
        plan.rooms = [
            FloorRoom(id="entry", room_type="entry", floor=1),
            FloorRoom(id="hall1", room_type="hall", floor=1),
            FloorRoom(id="ldk", room_type="ldk", floor=1),
            FloorRoom(id="bed1", room_type="bedroom", floor=1),
            FloorRoom(id="bed1_cl", room_type="closet", floor=1, parent_id="bed1"),
            FloorRoom(id="storage1", room_type="storage", floor=1),
            _make_fixed_room("toilet1", "toilet", 1),
            _make_fixed_room("wash1", "washroom", 1),
            _make_fixed_room("bath1", "bath", 1),
        ]

        result = allocate_floor(plan, metrics, "U_turn")

        assert len(result.errors) == 0
        # All variable rooms should have targets.
        for room in plan.rooms:
            if not room.is_fixed:
                assert room.id in result.room_targets
                target = result.room_targets[room.id]
                profile = ROOM_PROFILE.get(room.room_type)
                if profile:
                    assert target >= profile.min_jo * 0.9  # Allow rounding margin.
                    assert target <= profile.max_jo * 1.1

    def test_user_override_with_auto(self):
        """User locks master@12, rest auto-allocated."""
        metrics = compute_metrics(8.0, 9.0)
        plan = FloorPlan(floor=2, has_stair=True)
        plan.rooms = [
            FloorRoom(id="hall2", room_type="hall", floor=2),
            FloorRoom(id="master", room_type="master_bedroom", floor=2, target_jo=12.0),
            FloorRoom(id="bed2", room_type="bedroom", floor=2),
            FloorRoom(id="bed3", room_type="bedroom", floor=2),
            FloorRoom(id="master_cl", room_type="closet", floor=2, parent_id="master"),
            FloorRoom(id="bed2_cl", room_type="closet", floor=2, parent_id="bed2"),
            FloorRoom(id="bed3_cl", room_type="closet", floor=2, parent_id="bed3"),
            _make_fixed_room("toilet2", "toilet", 2),
            _make_fixed_room("wash2", "washroom", 2),
            _make_fixed_room("bath2", "bath", 2),
        ]

        result = allocate_floor(plan, metrics, "U_turn")

        assert result.room_targets["master"] == 12.0
        assert result.room_targets["bed2"] > 0
        assert result.room_targets["bed3"] > 0

    def test_large_envelope_triggers_max(self):
        """Large envelope → rooms may hit max clamp."""
        metrics = compute_metrics(10.0, 12.0)
        plan = FloorPlan(floor=1, has_stair=True)
        plan.rooms = [
            FloorRoom(id="entry", room_type="entry", floor=1),
            FloorRoom(id="hall1", room_type="hall", floor=1),
            FloorRoom(id="ldk", room_type="ldk", floor=1),
            FloorRoom(id="storage1", room_type="storage", floor=1),
            _make_fixed_room("toilet1", "toilet", 1),
            _make_fixed_room("wash1", "washroom", 1),
            _make_fixed_room("bath1", "bath", 1),
        ]

        result = allocate_floor(plan, metrics, "U_turn")

        # LDK should be capped at max.
        ldk_target = result.room_targets["ldk"]
        assert ldk_target <= ROOM_PROFILE["ldk"].max_jo + 0.5  # rounding tolerance

    def test_small_envelope_triggers_min(self):
        """Small envelope → rooms hit min clamp."""
        metrics = compute_metrics(6.0, 6.0)
        plan = FloorPlan(floor=2, has_stair=True)
        plan.rooms = [
            FloorRoom(id="hall2", room_type="hall", floor=2),
            FloorRoom(id="master", room_type="master_bedroom", floor=2),
            FloorRoom(id="bed2", room_type="bedroom", floor=2),
            FloorRoom(id="bed3", room_type="bedroom", floor=2),
            FloorRoom(id="bed4", room_type="bedroom", floor=2),
            FloorRoom(id="master_cl", room_type="closet", floor=2, parent_id="master"),
            FloorRoom(id="bed2_cl", room_type="closet", floor=2, parent_id="bed2"),
            FloorRoom(id="bed3_cl", room_type="closet", floor=2, parent_id="bed3"),
            FloorRoom(id="bed4_cl", room_type="closet", floor=2, parent_id="bed4"),
            _make_fixed_room("toilet2", "toilet", 2),
            _make_fixed_room("washstand2", "washstand", 2),
            _make_fixed_room("shower2", "shower", 2),
        ]

        result = allocate_floor(plan, metrics, "U_turn")

        # Rooms should be at or near minimum.
        for room in plan.rooms:
            if not room.is_fixed and room.id in result.room_targets:
                profile = ROOM_PROFILE.get(room.room_type)
                if profile:
                    assert result.room_targets[room.id] >= profile.min_jo * 0.9

    def test_no_errors_on_normal_config(self):
        """Normal config should produce no errors."""
        metrics = compute_metrics(9.1, 6.4)
        plan = FloorPlan(floor=1, has_stair=True)
        plan.rooms = [
            FloorRoom(id="entry", room_type="entry", floor=1),
            FloorRoom(id="hall1", room_type="hall", floor=1),
            FloorRoom(id="ldk", room_type="ldk", floor=1),
            FloorRoom(id="storage1", room_type="storage", floor=1),
            _make_fixed_room("toilet1", "toilet", 1),
            _make_fixed_room("wash1", "washroom", 1),
            _make_fixed_room("bath1", "bath", 1),
        ]

        result = allocate_floor(plan, metrics, "U_turn")
        assert len(result.errors) == 0
