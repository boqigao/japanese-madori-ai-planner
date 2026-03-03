"""Unit tests for the spec generator CLI and room spec parser."""

from __future__ import annotations

import pytest

from plan_engine.generator.cli import (
    RoomSpec,
    parse_args,
    parse_floor_spec,
    parse_room_spec,
    parse_rooms_shorthand,
)

# ---------------------------------------------------------------------------
# parse_room_spec — single room
# ---------------------------------------------------------------------------


class TestParseRoomSpecBasic:
    def test_simple_type(self):
        result = parse_room_spec("bedroom")
        assert result == [RoomSpec(room_type="bedroom")]

    def test_type_alias_bed(self):
        result = parse_room_spec("bed")
        assert result == [RoomSpec(room_type="bedroom")]

    def test_type_alias_master(self):
        result = parse_room_spec("master")
        assert result == [RoomSpec(room_type="master_bedroom")]

    def test_with_count(self):
        result = parse_room_spec("bed:3")
        assert result == [RoomSpec(room_type="bedroom", count=3)]

    def test_with_target(self):
        result = parse_room_spec("ldk@15")
        assert result == [RoomSpec(room_type="ldk", target_jo=15.0)]

    def test_with_target_decimal(self):
        result = parse_room_spec("bed@4.5")
        assert result == [RoomSpec(room_type="bedroom", target_jo=4.5)]

    def test_with_min_width(self):
        result = parse_room_spec("bed/1820")
        assert result == [RoomSpec(room_type="bedroom", min_width_mm=1820)]

    def test_count_and_target(self):
        result = parse_room_spec("bed:3@6")
        assert result == [RoomSpec(room_type="bedroom", count=3, target_jo=6.0)]

    def test_count_target_and_min_width(self):
        result = parse_room_spec("bed:3@6/1820")
        assert result == [
            RoomSpec(room_type="bedroom", count=3, target_jo=6.0, min_width_mm=1820)
        ]

    def test_target_and_min_width(self):
        result = parse_room_spec("ldk@15/2730")
        assert result == [RoomSpec(room_type="ldk", target_jo=15.0, min_width_mm=2730)]


# ---------------------------------------------------------------------------
# parse_room_spec — compound wet types
# ---------------------------------------------------------------------------


class TestParseRoomSpecCompound:
    def test_wash_bath(self):
        result = parse_room_spec("wash+bath")
        assert result == [
            RoomSpec(room_type="washroom"),
            RoomSpec(room_type="bath"),
        ]

    def test_ws_shower(self):
        result = parse_room_spec("ws+shower")
        assert result == [
            RoomSpec(room_type="washstand"),
            RoomSpec(room_type="shower"),
        ]


# ---------------------------------------------------------------------------
# parse_room_spec — attachment syntax
# ---------------------------------------------------------------------------


class TestParseRoomSpecAttachment:
    def test_master_plus_wic(self):
        result = parse_room_spec("master+wic")
        assert result == [
            RoomSpec(room_type="master_bedroom", attachment="wic"),
        ]

    def test_master_plus_wic_with_targets(self):
        result = parse_room_spec("master+wic@8+2")
        assert result == [
            RoomSpec(
                room_type="master_bedroom",
                target_jo=8.0,
                attachment="wic",
                attachment_target_jo=2.0,
            ),
        ]

    def test_master_plus_wic_with_targets_and_min_width(self):
        result = parse_room_spec("master+wic@8+2/2730")
        assert result == [
            RoomSpec(
                room_type="master_bedroom",
                target_jo=8.0,
                min_width_mm=2730,
                attachment="wic",
                attachment_target_jo=2.0,
            ),
        ]

    def test_bed_plus_cl(self):
        result = parse_room_spec("bed+cl")
        assert result == [
            RoomSpec(room_type="bedroom", attachment="closet"),
        ]

    def test_master_plus_wic_base_target_only(self):
        result = parse_room_spec("master+wic@8")
        assert result == [
            RoomSpec(
                room_type="master_bedroom",
                target_jo=8.0,
                attachment="wic",
            ),
        ]


# ---------------------------------------------------------------------------
# parse_room_spec — errors
# ---------------------------------------------------------------------------


class TestParseRoomSpecErrors:
    def test_empty_string(self):
        with pytest.raises(ValueError, match="invalid room spec"):
            parse_room_spec("")

    def test_invalid_format(self):
        with pytest.raises(ValueError, match="invalid room spec"):
            parse_room_spec("123abc")

    def test_uppercase_rejected(self):
        with pytest.raises(ValueError, match="invalid room spec"):
            parse_room_spec("BED")


# ---------------------------------------------------------------------------
# parse_floor_spec
# ---------------------------------------------------------------------------


class TestParseFloorSpec:
    def test_single_room(self):
        result = parse_floor_spec("ldk")
        assert result == [RoomSpec(room_type="ldk")]

    def test_comma_separated(self):
        result = parse_floor_spec("ldk@15, bed:3@6/1820, toilet, wash+bath")
        assert len(result) == 5  # ldk + 3*bed as 1 spec + toilet + washroom + bath
        assert result[0] == RoomSpec(room_type="ldk", target_jo=15.0)
        assert result[1] == RoomSpec(
            room_type="bedroom", count=3, target_jo=6.0, min_width_mm=1820
        )
        assert result[2] == RoomSpec(room_type="toilet")
        assert result[3] == RoomSpec(room_type="washroom")
        assert result[4] == RoomSpec(room_type="bath")

    def test_spaces_trimmed(self):
        result = parse_floor_spec("  ldk , bed  ")
        assert len(result) == 2

    def test_empty_string(self):
        result = parse_floor_spec("")
        assert result == []


# ---------------------------------------------------------------------------
# parse_rooms_shorthand
# ---------------------------------------------------------------------------


class TestParseRoomsShorthand:
    def test_5ldk(self):
        assert parse_rooms_shorthand("5ldk") == 5

    def test_3ldk_uppercase(self):
        assert parse_rooms_shorthand("3LDK") == 3

    def test_4ldk_mixed_case(self):
        assert parse_rooms_shorthand("4lDk") == 4

    def test_with_spaces(self):
        assert parse_rooms_shorthand(" 5ldk ") == 5

    def test_invalid_format(self):
        with pytest.raises(ValueError, match="invalid rooms shorthand"):
            parse_rooms_shorthand("abc")

    def test_missing_number(self):
        with pytest.raises(ValueError, match="invalid rooms shorthand"):
            parse_rooms_shorthand("ldk")


# ---------------------------------------------------------------------------
# parse_args — full CLI
# ---------------------------------------------------------------------------


class TestParseArgs:
    def test_minimal(self):
        args = parse_args(["--envelope", "8x9"])
        assert args.envelope_w_m == 8.0
        assert args.envelope_d_m == 9.0
        assert args.n_ldk is None
        assert args.floors == 2
        assert args.north == "top"
        assert args.stair_type == "U_turn"
        assert args.f1_specs is None
        assert args.f2_specs is None
        assert args.closets == "auto"

    def test_with_rooms(self):
        args = parse_args(["--envelope", "8x9", "--rooms", "5ldk"])
        assert args.n_ldk == 5

    def test_envelope_with_decimal(self):
        args = parse_args(["--envelope", "9.1x6.4"])
        assert args.envelope_w_m == 9.1
        assert args.envelope_d_m == 6.4

    def test_envelope_times_sign(self):
        args = parse_args(["--envelope", "8X9"])
        assert args.envelope_w_m == 8.0
        assert args.envelope_d_m == 9.0

    def test_with_f1_f2(self):
        args = parse_args([
            "--envelope", "8x9",
            "--f1", "ldk@15, toilet, wash+bath",
            "--f2", "master+wic@8+2, bed:2@6, toilet, ws+shower",
        ])
        assert args.f1_specs is not None
        assert len(args.f1_specs) == 4  # ldk + toilet + washroom + bath
        assert args.f2_specs is not None
        assert len(args.f2_specs) == 5  # master+wic + bed:2 + toilet + washstand + shower

    def test_with_floors_and_north(self):
        args = parse_args([
            "--envelope", "12x8",
            "--floors", "1",
            "--north", "left",
        ])
        assert args.floors == 1
        assert args.north == "left"

    def test_with_stair_and_closets(self):
        args = parse_args([
            "--envelope", "8x9",
            "--stair", "straight",
            "--closets", "none",
        ])
        assert args.stair_type == "straight"
        assert args.closets == "none"

    def test_invalid_envelope(self):
        with pytest.raises(ValueError, match="invalid envelope"):
            parse_args(["--envelope", "bad"])
