"""Unit tests for Stage 2 & 3: room distribution and wet selection."""

from __future__ import annotations

from plan_engine.generator.cli import GeneratorArgs, parse_floor_spec
from plan_engine.generator.distribute import (
    FloorPlan,
    FloorRoom,
    _distribute_bedrooms,
    _make_fixed_room,
    distribute_rooms,
    select_wet_modules,
)
from plan_engine.generator.metrics import FloorMetrics, compute_metrics

# ---------------------------------------------------------------------------
# Bedroom distribution
# ---------------------------------------------------------------------------


class TestBedroomDistribution:
    def test_5ldk_8x9(self):
        """5LDK on 8x9 → expect some beds on F1 and rest on F2."""
        metrics = compute_metrics(8.0, 9.0)
        f1, f2 = _distribute_bedrooms(5, metrics, "U_turn", 2)
        assert f1 + f2 == 5
        assert f2 >= 1  # At least 1 bedroom on F2.
        assert f1 >= 0

    def test_3ldk_9x6(self):
        """3LDK on 9.1x6.4 → all 3 on F2."""
        metrics = compute_metrics(9.1, 6.4)
        f1, f2 = _distribute_bedrooms(3, metrics, "U_turn", 2)
        assert f1 + f2 == 3
        assert f2 == 3  # All fit on F2.
        assert f1 == 0

    def test_4ldk_10x8(self):
        """4LDK on 10x8 → all 4 should fit on F2."""
        metrics = compute_metrics(10.0, 8.0)
        f1, f2 = _distribute_bedrooms(4, metrics, "U_turn", 2)
        assert f1 + f2 == 4
        assert f2 >= 3  # At least 3 on F2.

    def test_1f_all_on_f1(self):
        """1F mode → all bedrooms on F1."""
        metrics = compute_metrics(12.0, 8.0)
        f1, f2 = _distribute_bedrooms(3, metrics, "U_turn", 1)
        assert f1 == 3
        assert f2 == 0


# ---------------------------------------------------------------------------
# Full distribution via distribute_rooms
# ---------------------------------------------------------------------------


class TestDistributeRooms:
    def test_5ldk_shorthand(self):
        """--rooms 5ldk produces F1 and F2 plans with correct room counts."""
        args = GeneratorArgs(
            envelope_w_m=8.0,
            envelope_d_m=9.0,
            n_ldk=5,
        )
        metrics = compute_metrics(8.0, 9.0)
        plans = distribute_rooms(args, metrics)

        assert len(plans) == 2
        f1, f2 = plans

        # F1 must have entry, hall, ldk.
        f1_types = {r.room_type for r in f1.rooms}
        assert "entry" in f1_types
        assert "hall" in f1_types
        assert "ldk" in f1_types

        # F2 must have master bedroom.
        f2_types = {r.room_type for r in f2.rooms}
        assert "master_bedroom" in f2_types
        assert "hall" in f2_types

        # Total bedrooms across both floors = 5.
        total_beds = sum(
            1 for p in plans for r in p.rooms
            if r.room_type in ("bedroom", "master_bedroom")
        )
        assert total_beds == 5

    def test_3ldk_shorthand(self):
        """--rooms 3ldk → 0 F1 beds, 3 F2 beds (master + 2)."""
        args = GeneratorArgs(
            envelope_w_m=9.1,
            envelope_d_m=6.4,
            n_ldk=3,
        )
        metrics = compute_metrics(9.1, 6.4)
        plans = distribute_rooms(args, metrics)

        f1, f2 = plans
        f1_beds = [r for r in f1.rooms if r.room_type in ("bedroom", "master_bedroom")]
        f2_beds = [r for r in f2.rooms if r.room_type in ("bedroom", "master_bedroom")]
        assert len(f1_beds) == 0
        assert len(f2_beds) == 3

    def test_f1_f2_override(self):
        """--f1/--f2 overrides take full priority."""
        f1_specs = parse_floor_spec("ldk@15, bed@6, toilet, wash+bath")
        f2_specs = parse_floor_spec("master@8, bed:2@6, toilet, ws+shower")
        args = GeneratorArgs(
            envelope_w_m=8.0,
            envelope_d_m=9.0,
            n_ldk=5,  # Should be ignored.
            f1_specs=f1_specs,
            f2_specs=f2_specs,
        )
        metrics = compute_metrics(8.0, 9.0)
        plans = distribute_rooms(args, metrics)

        f1, f2 = plans
        # F1 should have exactly what was specified.
        f1_types = [r.room_type for r in f1.rooms]
        assert "ldk" in f1_types
        assert f1_types.count("bedroom") == 1

        # F2 should have master + 2 beds.
        f2_bed_types = [r.room_type for r in f2.rooms if r.room_type in ("bedroom", "master_bedroom")]
        assert len(f2_bed_types) == 3

    def test_1f_mode(self):
        """--floors 1 produces only F1."""
        args = GeneratorArgs(
            envelope_w_m=12.0,
            envelope_d_m=8.0,
            n_ldk=3,
            floors=1,
        )
        metrics = compute_metrics(12.0, 8.0)
        plans = distribute_rooms(args, metrics)

        assert len(plans) == 1
        f1 = plans[0]
        total_beds = sum(
            1 for r in f1.rooms
            if r.room_type in ("bedroom", "master_bedroom")
        )
        assert total_beds == 3

    def test_auto_closets(self):
        """Auto closets are generated for each bedroom."""
        args = GeneratorArgs(
            envelope_w_m=9.1,
            envelope_d_m=6.4,
            n_ldk=3,
            closets="auto",
        )
        metrics = compute_metrics(9.1, 6.4)
        plans = distribute_rooms(args, metrics)

        f2 = plans[1]
        closets = [r for r in f2.rooms if r.room_type == "closet"]
        beds = [r for r in f2.rooms if r.room_type in ("bedroom", "master_bedroom")]
        assert len(closets) == len(beds)
        # Each closet has a parent_id.
        for cl in closets:
            assert cl.parent_id is not None

    def test_closets_none(self):
        """--closets none → no auto closets."""
        args = GeneratorArgs(
            envelope_w_m=9.1,
            envelope_d_m=6.4,
            n_ldk=3,
            closets="none",
        )
        metrics = compute_metrics(9.1, 6.4)
        plans = distribute_rooms(args, metrics)

        f2 = plans[1]
        closets = [r for r in f2.rooms if r.room_type == "closet"]
        assert len(closets) == 0


# ---------------------------------------------------------------------------
# Wet module selection (Stage 3)
# ---------------------------------------------------------------------------


class TestWetSelection:
    def _make_tight_f2(self, metrics: FloorMetrics) -> FloorPlan:
        """Create a tight F2 with many bedrooms to trigger compact wet."""
        plan = FloorPlan(floor=2, has_stair=True)
        plan.rooms.append(FloorRoom(id="hall2", room_type="hall", floor=2))
        plan.rooms.append(FloorRoom(id="master", room_type="master_bedroom", floor=2))
        for i in range(2, 6):
            plan.rooms.append(FloorRoom(id=f"bed{i}", room_type="bedroom", floor=2))
            plan.rooms.append(FloorRoom(id=f"bed{i}_cl", room_type="closet", floor=2, parent_id=f"bed{i}"))
        plan.rooms.append(FloorRoom(id="master_cl", room_type="closet", floor=2, parent_id="master"))
        plan.rooms.append(_make_fixed_room("toilet2", "toilet", 2))
        plan.rooms.append(_make_fixed_room("wash2", "washroom", 2))
        plan.rooms.append(_make_fixed_room("bath2", "bath", 2))
        return plan

    def _make_spacious_f2(self, metrics: FloorMetrics) -> FloorPlan:
        """Create a spacious F2 with few bedrooms."""
        plan = FloorPlan(floor=2, has_stair=True)
        plan.rooms.append(FloorRoom(id="hall2", room_type="hall", floor=2))
        plan.rooms.append(FloorRoom(id="master", room_type="master_bedroom", floor=2))
        plan.rooms.append(FloorRoom(id="bed2", room_type="bedroom", floor=2))
        plan.rooms.append(_make_fixed_room("toilet2", "toilet", 2))
        plan.rooms.append(_make_fixed_room("wash2", "washroom", 2))
        plan.rooms.append(_make_fixed_room("bath2", "bath", 2))
        return plan

    def test_tight_f2_switches_to_compact(self):
        """Tight F2 (many bedrooms, small envelope) → compact wet."""
        metrics = compute_metrics(7.0, 7.0)  # Small envelope.
        plan = self._make_tight_f2(metrics)
        select_wet_modules(plan, metrics, "U_turn")

        wet_types = {r.room_type for r in plan.rooms}
        assert "washstand" in wet_types
        assert "shower" in wet_types
        assert "washroom" not in wet_types
        assert "bath" not in wet_types
        assert plan.wet_type == "compact"

    def test_spacious_f2_keeps_standard(self):
        """Spacious F2 (few bedrooms, large envelope) → standard wet."""
        metrics = compute_metrics(10.0, 10.0)  # Large envelope.
        plan = self._make_spacious_f2(metrics)
        select_wet_modules(plan, metrics, "U_turn")

        wet_types = {r.room_type for r in plan.rooms}
        assert "washroom" in wet_types
        assert "bath" in wet_types
        assert plan.wet_type == "standard"

    def test_user_explicit_wet_not_replaced(self):
        """User-specified wet rooms are not replaced by auto-selection."""
        f2_specs = parse_floor_spec("master, bed:2, toilet, wash+bath")
        args = GeneratorArgs(
            envelope_w_m=7.0,
            envelope_d_m=7.0,
            f2_specs=f2_specs,
        )
        metrics = compute_metrics(7.0, 7.0)
        plans = distribute_rooms(args, metrics)

        f2 = plans[1]
        wet_types = {r.room_type for r in f2.rooms}
        # User specified wash+bath → should NOT be replaced.
        assert "washroom" in wet_types
        assert "bath" in wet_types
