"""CLI argument parsing and room spec mini-language parser."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass


@dataclass
class RoomSpec:
    """Parsed room specification from CLI mini-language.

    Attributes:
        room_type: Canonical room type (e.g., "bedroom", "ldk").
        count: Number of rooms of this type.
        target_jo: User-specified target in tatami, or None for auto.
        min_width_mm: User-specified minimum width in mm, or None for default.
        attachment: Attachment type (e.g., "wic", "cl"), or None.
        attachment_target_jo: Target tatami for the attachment, or None for auto.
    """

    room_type: str
    count: int = 1
    target_jo: float | None = None
    min_width_mm: int | None = None
    attachment: str | None = None
    attachment_target_jo: float | None = None


@dataclass
class GeneratorArgs:
    """Parsed CLI arguments for the spec generator.

    Attributes:
        envelope_w_m: Envelope width in meters.
        envelope_d_m: Envelope depth in meters.
        n_ldk: Number of bedrooms from --rooms shorthand, or None.
        floors: Number of floors.
        north: North direction.
        stair_type: Stair type string.
        f1_specs: Parsed room specs for F1, or None for auto.
        f2_specs: Parsed room specs for F2, or None for auto.
        closets: Closet mode ("auto" or "none").
        output: Output file path.
    """

    envelope_w_m: float
    envelope_d_m: float
    n_ldk: int | None = None
    floors: int = 2
    north: str = "top"
    stair_type: str = "U_turn"
    stair_type_explicit: bool = False
    f1_specs: list[RoomSpec] | None = None
    f2_specs: list[RoomSpec] | None = None
    closets: str = "auto"
    output: str = "spec.yaml"


# Compound wet type expansions.
_WET_COMPOUNDS: dict[str, list[str]] = {
    "wash+bath": ["washroom", "bath"],
    "ws+shower": ["washstand", "shower"],
}

# Type aliases for CLI shorthand.
_TYPE_ALIASES: dict[str, str] = {
    "bed": "bedroom",
    "master": "master_bedroom",
}

# Room spec pattern: type[:count][@target][/min_width]
_ROOM_SPEC_RE = re.compile(
    r"^(?P<type>[a-z_]+)"
    r"(?::(?P<count>\d+))?"
    r"(?:@(?P<target>[0-9.]+))?"
    r"(?:/(?P<min_width>\d+))?$"
)


def parse_room_spec(token: str) -> list[RoomSpec]:
    """Parse a single room spec token into one or more RoomSpec objects.

    Args:
        token: Room spec string (e.g., "bed:3@6/1820", "master+wic@8+2", "wash+bath").

    Returns:
        List of parsed RoomSpec objects.

    Raises:
        ValueError: If the token cannot be parsed.
    """
    token = token.strip()

    # Handle compound wet types first.
    if token in _WET_COMPOUNDS:
        return [RoomSpec(room_type=t) for t in _WET_COMPOUNDS[token]]

    # Handle attachment syntax: type+attachment[@target+attach_target][/min_width]
    if "+" in token:
        return _parse_attachment_spec(token)

    match = _ROOM_SPEC_RE.match(token)
    if not match:
        raise ValueError(f"invalid room spec: '{token}'")

    raw_type = match.group("type")
    room_type = _TYPE_ALIASES.get(raw_type, raw_type)
    count = int(match.group("count")) if match.group("count") else 1
    target = float(match.group("target")) if match.group("target") else None
    min_width = int(match.group("min_width")) if match.group("min_width") else None

    return [RoomSpec(room_type=room_type, count=count, target_jo=target, min_width_mm=min_width)]


def _parse_attachment_spec(token: str) -> list[RoomSpec]:
    """Parse room+attachment syntax like 'master+wic@8+2/2730'.

    Supported formats:
        master+wic          → master (auto) + wic (auto)
        master+wic@8+2      → master (8jo) + wic (2jo)
        master+wic@8+2/2730 → master (8jo, 2730mm) + wic (2jo)
    """
    # Split the attachment from base type.
    # Find the first + that's in the type portion (before any @).
    at_pos = token.find("@")
    slash_pos = token.find("/")

    # Get the type+attach portion (before @ or end).
    type_end = at_pos if at_pos >= 0 else (slash_pos if slash_pos >= 0 else len(token))
    type_part = token[:type_end]

    if "+" not in type_part:
        # The + is inside @target portion, handle as compound wet.
        if token in _WET_COMPOUNDS:
            return [RoomSpec(room_type=t) for t in _WET_COMPOUNDS[token]]
        raise ValueError(f"invalid room spec with '+': '{token}'")

    base_type, attach_type = type_part.split("+", 1)
    base_type = _TYPE_ALIASES.get(base_type, base_type)

    # Map attachment shorthand.
    attach_type_map = {"wic": "wic", "cl": "closet"}
    attach_room_type = attach_type_map.get(attach_type, attach_type)

    base_target: float | None = None
    attach_target: float | None = None
    min_width: int | None = None

    # Parse @target+attach_target if present.
    remaining = token[type_end:]
    if remaining.startswith("@"):
        remaining = remaining[1:]
        # Split on / for min_width.
        if "/" in remaining:
            target_part, width_str = remaining.split("/", 1)
            min_width = int(width_str)
        else:
            target_part = remaining

        # Split targets on +.
        if "+" in target_part:
            base_str, attach_str = target_part.split("+", 1)
            base_target = float(base_str)
            attach_target = float(attach_str)
        else:
            base_target = float(target_part)
    elif remaining.startswith("/"):
        min_width = int(remaining[1:])

    return [
        RoomSpec(
            room_type=base_type,
            target_jo=base_target,
            min_width_mm=min_width,
            attachment=attach_room_type,
            attachment_target_jo=attach_target,
        ),
    ]


def parse_floor_spec(spec_str: str) -> list[RoomSpec]:
    """Parse a comma-separated floor specification string.

    Args:
        spec_str: Floor spec like "ldk@15, bed:3@6/1820, toilet, wash+bath".

    Returns:
        List of parsed RoomSpec objects.

    Raises:
        ValueError: If any token cannot be parsed.
    """
    tokens = [t.strip() for t in spec_str.split(",") if t.strip()]
    result: list[RoomSpec] = []
    for token in tokens:
        result.extend(parse_room_spec(token))
    return result


def parse_rooms_shorthand(shorthand: str) -> int:
    """Parse --rooms shorthand like '5ldk' into bedroom count.

    Args:
        shorthand: String like "5ldk", "3LDK", "4ldk".

    Returns:
        Number of bedrooms (the N in NlDK).

    Raises:
        ValueError: If the shorthand cannot be parsed.
    """
    match = re.match(r"^(\d+)\s*[lL][dD][kK]$", shorthand.strip())
    if not match:
        raise ValueError(f"invalid rooms shorthand: '{shorthand}' (expected format: NlDK, e.g., '5ldk')")
    return int(match.group(1))


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the argparse parser for gen_spec.py."""
    parser = argparse.ArgumentParser(
        description="Generate a spec.yaml from high-level requirements.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--envelope",
        required=True,
        help="Envelope dimensions in meters (WxD), e.g., '8x9' or '9.1x6.4'",
    )
    parser.add_argument(
        "--rooms",
        help="Room shorthand (e.g., '5ldk', '3ldk')",
    )
    parser.add_argument(
        "--floors",
        type=int,
        default=2,
        help="Number of floors (default: 2)",
    )
    parser.add_argument(
        "--north",
        default="top",
        choices=["top", "bottom", "left", "right"],
        help="North direction (default: top)",
    )
    parser.add_argument(
        "--stair",
        default=None,
        choices=["straight", "L_landing", "U_turn"],
        help="Stair type (default: auto-selected by lot width)",
    )
    parser.add_argument(
        "--f1",
        help="F1 room specification (e.g., 'ldk@15, bed, toilet, wash+bath')",
    )
    parser.add_argument(
        "--f2",
        help="F2 room specification (e.g., 'master@8, bed:3@6, toilet, ws+shower')",
    )
    parser.add_argument(
        "--closets",
        default="auto",
        choices=["auto", "none"],
        help="Closet generation mode (default: auto)",
    )
    parser.add_argument(
        "--output",
        default="spec.yaml",
        help="Output file path (default: spec.yaml)",
    )
    return parser


def parse_args(argv: list[str] | None = None) -> GeneratorArgs:
    """Parse CLI arguments into a GeneratorArgs dataclass.

    Args:
        argv: Argument list (defaults to sys.argv[1:]).

    Returns:
        Parsed GeneratorArgs.

    Raises:
        ValueError: If arguments are invalid.
    """
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    # Parse envelope.
    envelope_match = re.match(r"^([0-9.]+)\s*[xX×]\s*([0-9.]+)$", args.envelope)
    if not envelope_match:
        raise ValueError(f"invalid envelope format: '{args.envelope}' (expected WxD, e.g., '8x9')")
    envelope_w_m = float(envelope_match.group(1))
    envelope_d_m = float(envelope_match.group(2))

    # Parse --rooms shorthand.
    n_ldk: int | None = None
    if args.rooms:
        n_ldk = parse_rooms_shorthand(args.rooms)

    # Parse per-floor specs.
    f1_specs = parse_floor_spec(args.f1) if args.f1 else None
    f2_specs = parse_floor_spec(args.f2) if args.f2 else None

    stair_explicit = args.stair is not None
    stair_type = args.stair if stair_explicit else "U_turn"

    return GeneratorArgs(
        envelope_w_m=envelope_w_m,
        envelope_d_m=envelope_d_m,
        n_ldk=n_ldk,
        floors=args.floors,
        north=args.north,
        stair_type=stair_type,
        stair_type_explicit=stair_explicit,
        f1_specs=f1_specs,
        f2_specs=f2_specs,
        closets=args.closets,
        output=args.output,
    )
