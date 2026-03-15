"""YAML spec emission and feasibility self-check."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from plan_engine.generator.allocate import allocate_floor
from plan_engine.generator.profiles import (
    DEFAULT_FLOOR_HEIGHT_MM,
    DEFAULT_RISER_PREF_MM,
    DEFAULT_STAIR_WIDTH_MM,
    DEFAULT_TREAD_PREF_MM,
    MIN_WIDTH_DEFAULTS,
    STAIR_CELLS_ESTIMATE,
)
from plan_engine.generator.topology import generate_topology

if TYPE_CHECKING:
    from plan_engine.generator.allocate import AllocationResult
    from plan_engine.generator.distribute import FloorPlan, FloorRoom
    from plan_engine.generator.metrics import FloorMetrics


@dataclass
class FeasibilityReport:
    """Feasibility self-check results.

    Attributes:
        floor_summaries: Per-floor summary lines.
        warnings: Warning messages.
        errors: Error messages.
    """

    floor_summaries: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    stair_type: str | None = None

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0


def _build_space_dict(
    room: FloorRoom,
    target_jo: float | None,
) -> dict[str, Any]:
    """Build a single space dict for YAML emission."""
    space: dict[str, Any] = {"id": room.id, "type": room.room_type}

    if room.parent_id:
        space["parent_id"] = room.parent_id

    if room.is_fixed:
        # Fixed rooms (toilet, washroom, bath, etc.) have no area/size_constraints.
        return space

    # Size constraints.
    min_width = room.min_width_mm or MIN_WIDTH_DEFAULTS.get(room.room_type)
    if min_width:
        space["size_constraints"] = {"min_width": min_width}

    # Area.
    if target_jo is not None:
        space["area"] = {"target_tatami": target_jo}

    # Shape for halls and LDK.
    if room.room_type == "hall":
        space["shape"] = {"allow": ["L2"], "rect_components_max": 3}
    elif room.room_type == "ldk":
        space["shape"] = {"allow": ["L2"], "rect_components_max": 2}

    return space


def _build_floor_dict(
    plan: FloorPlan,
    allocation: AllocationResult,
    stair_type: str,
    is_first_floor: bool,
    floors_total: int,
) -> dict[str, Any]:
    """Build a single floor dict for YAML emission."""
    floor_dict: dict[str, Any] = {}

    # Core (stair) — only on F1 for 2F specs.
    if is_first_floor and floors_total >= 2:
        floor_dict["core"] = {
            "stair": {
                "id": "stair",
                "type": stair_type,
                "width": DEFAULT_STAIR_WIDTH_MM,
                "floor_height": DEFAULT_FLOOR_HEIGHT_MM,
                "riser_pref": DEFAULT_RISER_PREF_MM,
                "tread_pref": DEFAULT_TREAD_PREF_MM,
                "connects": {"F1": "hall1", "F2": "hall2"},
            }
        }

    # Spaces.
    spaces: list[dict[str, Any]] = []
    for room in plan.rooms:
        target = allocation.room_targets.get(room.id)
        spaces.append(_build_space_dict(room, target))
    floor_dict["spaces"] = spaces

    # Topology.
    edges = generate_topology(plan)
    if edges:
        adj_list = [[e.left, e.right, e.strength] for e in edges]
        floor_dict["topology"] = {"adjacency": adj_list}

    return floor_dict


def build_spec(
    metrics: FloorMetrics,
    plans: list[FloorPlan],
    stair_type: str,
    north: str,
) -> tuple[dict[str, Any], FeasibilityReport]:
    """Build a complete spec dict and run feasibility check.

    Returns:
        (spec_dict, feasibility_report) tuple.
    """
    report = FeasibilityReport(stair_type=stair_type)

    spec: dict[str, Any] = {
        "version": 0.2,
        "units": "mm",
        "grid": {"minor": 455, "major": 910},
        "site": {
            "envelope": {
                "type": "rectangle",
                "width": metrics.envelope_w_mm,
                "depth": metrics.envelope_d_mm,
            },
            "north": north,
        },
    }

    floors_dict: dict[str, Any] = {}
    floors_total = len(plans)

    for plan in plans:
        # Allocate area.
        allocation = allocate_floor(plan, metrics, stair_type)
        report.warnings.extend(allocation.warnings)
        report.errors.extend(allocation.errors)

        # Compute density for summary.
        density = _compute_density(plan, allocation, metrics, stair_type)

        summary = (
            f"F{plan.floor}: "
            f"{len(plan.rooms)} rooms, "
            f"available={allocation.available_jo:.1f}jo, "
            f"allocated={allocation.allocated_jo:.1f}jo, "
            f"density={density:.0%}"
        )
        report.floor_summaries.append(summary)

        # Density warnings.
        if density > 0.85:
            report.warnings.append(
                f"F{plan.floor}: density {density:.0%} > 85% — "
                f"consider compact wet, fewer rooms, or larger envelope"
            )
        elif density < 0.60 and plan.floor == 1:
            report.warnings.append(
                f"F{plan.floor}: density {density:.0%} < 60% — "
                f"consider adding storage or WIC to absorb excess area"
            )

        # Build floor dict.
        floor_key = f"F{plan.floor}"
        floors_dict[floor_key] = _build_floor_dict(
            plan, allocation, stair_type,
            is_first_floor=(plan.floor == 1),
            floors_total=floors_total,
        )

    spec["floors"] = floors_dict
    return spec, report


def _compute_density(
    plan: FloorPlan,
    allocation: AllocationResult,
    metrics: FloorMetrics,
    stair_type: str,
) -> float:
    """Compute target density: allocated / available total."""
    total_jo = metrics.area_jo
    if total_jo <= 0:
        return 1.0

    # Fixed rooms + stair + allocated variable rooms.
    used_jo = allocation.allocated_jo
    for room in plan.rooms:
        if room.is_fixed and room.fixed_w_mm and room.fixed_d_mm:
            used_jo += (room.fixed_w_mm * room.fixed_d_mm) / 1_620_000
    if plan.has_stair:
        stair_cells = STAIR_CELLS_ESTIMATE.get(stair_type, 12)
        used_jo += stair_cells * 910 * 910 / 1_620_000

    return used_jo / total_jo


def emit_yaml(spec: dict[str, Any], output_path: str) -> None:
    """Write spec dict to a YAML file."""
    with Path(output_path).open("w") as f:
        yaml.safe_dump(spec, f, default_flow_style=None, sort_keys=False)


def print_report(report: FeasibilityReport) -> None:
    """Print feasibility report to stderr."""
    print("\n=== Feasibility Report ===", file=sys.stderr)
    if report.stair_type:
        print(f"  Stair type: {report.stair_type}", file=sys.stderr)
    for summary in report.floor_summaries:
        print(f"  {summary}", file=sys.stderr)

    if report.warnings:
        print("\nWarnings:", file=sys.stderr)
        for w in report.warnings:
            print(f"  ⚠ {w}", file=sys.stderr)

    if report.errors:
        print("\nErrors:", file=sys.stderr)
        for e in report.errors:
            print(f"  ✗ {e}", file=sys.stderr)
    elif not report.warnings:
        print("\n  ✓ All checks passed", file=sys.stderr)

    print(file=sys.stderr)
