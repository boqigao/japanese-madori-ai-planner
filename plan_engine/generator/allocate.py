"""Stage 4: Proportional area allocation with min/max clamps."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from plan_engine.constants import MAJOR_GRID_MM, TATAMI_MM2
from plan_engine.generator.profiles import (
    ROOM_PROFILE,
    STAIR_CELLS_ESTIMATE,
)

if TYPE_CHECKING:
    from plan_engine.generator.distribute import FloorPlan, FloorRoom
    from plan_engine.generator.metrics import FloorMetrics


@dataclass
class AllocationResult:
    """Result of area allocation for one floor.

    Attributes:
        room_targets: Map from room ID to allocated target in tatami.
        available_jo: Total available tatami for variable rooms.
        allocated_jo: Total allocated tatami.
        excess_jo: Unallocated excess (positive) or deficit (negative).
        warnings: List of warning messages.
        errors: List of error messages.
    """

    room_targets: dict[str, float]
    available_jo: float
    allocated_jo: float
    excess_jo: float
    warnings: list[str]
    errors: list[str]


def _round_to_half_jo(value: float) -> float:
    """Round a tatami value to the nearest 0.5 increment."""
    return round(value * 2) / 2


def _compute_available_jo(
    plan: FloorPlan,
    metrics: FloorMetrics,
    stair_type: str,
) -> float:
    """Compute available tatami for variable-size rooms.

    Deducts fixed rooms (wet, toilet) and stair from total floor area.
    """
    total_jo = metrics.area_jo

    # Deduct stair.
    if plan.has_stair:
        stair_cells = STAIR_CELLS_ESTIMATE.get(stair_type, 12)
        stair_jo = stair_cells * MAJOR_GRID_MM * MAJOR_GRID_MM / TATAMI_MM2
        total_jo -= stair_jo

    # Deduct fixed rooms.
    for room in plan.rooms:
        if room.is_fixed and room.fixed_w_mm and room.fixed_d_mm:
            room_jo = (room.fixed_w_mm * room.fixed_d_mm) / TATAMI_MM2
            total_jo -= room_jo

    return max(0.0, total_jo)


def allocate_floor(
    plan: FloorPlan,
    metrics: FloorMetrics,
    stair_type: str,
) -> AllocationResult:
    """Allocate area to variable-size rooms on a single floor.

    Algorithm:
    1. Compute available tatami (total minus fixed rooms and stair).
    2. Deduct user-locked @target values.
    3. Distribute remainder proportionally by weight.
    4. Clamp to [min, max] bounds.
    5. Redistribute excess from clamped rooms (iterative).
    6. Round to 0.5 jo increments.

    Returns:
        AllocationResult with per-room targets and diagnostics.
    """
    warnings: list[str] = []
    errors: list[str] = []

    available_jo = _compute_available_jo(plan, metrics, stair_type)

    # Separate rooms into user-locked and auto-allocated.
    locked: dict[str, float] = {}
    auto_rooms: list[FloorRoom] = []

    for room in plan.rooms:
        if room.is_fixed:
            continue
        if room.target_jo is not None:
            locked[room.id] = room.target_jo
        else:
            auto_rooms.append(room)

    # Deduct locked values.
    locked_total = sum(locked.values())
    remainder = available_jo - locked_total

    if remainder < 0:
        errors.append(
            f"User-locked targets ({locked_total:.1f}jo) exceed "
            f"available space ({available_jo:.1f}jo) by {-remainder:.1f}jo"
        )
        remainder = 0.0

    # Proportional distribution with min/max clamping (iterative).
    room_targets: dict[str, float] = dict(locked)
    targets = _proportional_allocate(auto_rooms, remainder)
    room_targets.update(targets)

    # Compute totals.
    allocated_jo = sum(room_targets.values())
    excess_jo = available_jo - allocated_jo

    # Warnings.
    if excess_jo > 3.0:
        warnings.append(
            f"Floor {plan.floor}: {excess_jo:.1f}jo unallocated "
            f"(consider adding storage or WIC)"
        )
    if excess_jo < -1.0:
        warnings.append(
            f"Floor {plan.floor}: over-allocated by {-excess_jo:.1f}jo "
            f"(consider removing a room or enlarging envelope)"
        )

    return AllocationResult(
        room_targets=room_targets,
        available_jo=available_jo,
        allocated_jo=allocated_jo,
        excess_jo=excess_jo,
        warnings=warnings,
        errors=errors,
    )


def _proportional_allocate(
    rooms: list[FloorRoom],
    available: float,
) -> dict[str, float]:
    """Distribute available tatami proportionally by weight with clamping.

    Iterates until no more rooms hit their clamp bounds.
    """
    if not rooms:
        return {}

    result: dict[str, float] = {}
    remaining = available
    unclamped = list(rooms)

    for _ in range(10):  # Max iterations to prevent infinite loops.
        total_weight = sum(
            ROOM_PROFILE[r.room_type].weight
            for r in unclamped
            if r.room_type in ROOM_PROFILE
        )
        if total_weight <= 0:
            break

        newly_clamped: list[FloorRoom] = []
        for room in unclamped:
            profile = ROOM_PROFILE.get(room.room_type)
            if not profile:
                # Unknown room type — give it a small default.
                result[room.id] = _round_to_half_jo(1.5)
                remaining -= 1.5
                newly_clamped.append(room)
                continue

            share = (profile.weight / total_weight) * remaining
            if share < profile.min_jo:
                result[room.id] = _round_to_half_jo(profile.min_jo)
                remaining -= profile.min_jo
                newly_clamped.append(room)
            elif share > profile.max_jo:
                result[room.id] = _round_to_half_jo(profile.max_jo)
                remaining -= profile.max_jo
                newly_clamped.append(room)

        if not newly_clamped:
            # No clamping needed — distribute remainder.
            for room in unclamped:
                profile = ROOM_PROFILE.get(room.room_type)
                if profile:
                    share = (profile.weight / total_weight) * remaining
                    result[room.id] = _round_to_half_jo(share)
            break

        unclamped = [r for r in unclamped if r not in newly_clamped]
        if not unclamped:
            break

    return result
