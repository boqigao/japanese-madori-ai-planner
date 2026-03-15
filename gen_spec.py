#!/usr/bin/env python3
"""Generate a spec.yaml from high-level requirements.

Usage:
    uv run python gen_spec.py --envelope 8x9 --rooms 5ldk
    uv run python gen_spec.py --envelope 9.1x6.4 --rooms 3ldk --output my_spec.yaml
    uv run python gen_spec.py --envelope 8x9 --f1 "ldk@18, bed, toilet, wash+bath" --f2 "master+wic@8+2, bed:3@6, toilet, ws+shower"
"""

from __future__ import annotations

import sys

from plan_engine.generator.cli import parse_args
from plan_engine.generator.distribute import distribute_rooms
from plan_engine.generator.emit import build_spec, emit_yaml, print_report
from plan_engine.generator.metrics import compute_metrics
from plan_engine.generator.profiles import select_stair_type


def main(argv: list[str] | None = None) -> int:
    """Run the spec generator pipeline."""
    try:
        args = parse_args(argv)
    except (ValueError, SystemExit) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Stage 1: Metrics.
    metrics = compute_metrics(args.envelope_w_m, args.envelope_d_m)
    print(
        f"Envelope: {args.envelope_w_m}m × {args.envelope_d_m}m "
        f"→ {metrics.envelope_w_mm}×{metrics.envelope_d_mm}mm "
        f"({metrics.cols}×{metrics.rows} grid, {metrics.area_jo:.1f}jo/floor)",
        file=sys.stderr,
    )

    # Auto-select stair type based on lot width (skip for 1F or explicit --stair).
    if not args.stair_type_explicit and args.floors >= 2:
        args.stair_type = select_stair_type(metrics.envelope_w_mm)
        print(f"Stair: auto-selected '{args.stair_type}'", file=sys.stderr)
    elif args.floors >= 2:
        print(f"Stair: '{args.stair_type}' (user-specified)", file=sys.stderr)

    # Stage 2 & 3: Distribution and wet selection.
    plans = distribute_rooms(args, metrics)
    for plan in plans:
        bed_count = sum(
            1 for r in plan.rooms
            if r.room_type in ("bedroom", "master_bedroom")
        )
        room_count = len(plan.rooms)
        print(
            f"F{plan.floor}: {room_count} rooms, {bed_count} bedrooms, "
            f"wet={plan.wet_type}",
            file=sys.stderr,
        )

    # Stage 4 & 5: Allocation, topology, and YAML emission.
    spec, report = build_spec(metrics, plans, args.stair_type, args.north)

    # Print feasibility report.
    print_report(report)

    if not report.ok:
        print(
            "Spec generation failed due to errors. "
            "Try reducing rooms or enlarging the envelope.",
            file=sys.stderr,
        )
        return 1

    # Write YAML.
    emit_yaml(spec, args.output)
    print(f"Wrote {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
