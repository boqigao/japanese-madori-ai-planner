"""Stage 2 & 3: Room distribution across floors and wet module selection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from plan_engine.generator.profiles import (
    COMPACT_WET_DENSITY_THRESHOLD,
    ROOM_PROFILE,
    ROOM_WEIGHT_CELLS,
    STAIR_CELLS_ESTIMATE,
    WET_FIXED_SIZES_MM,
)

if TYPE_CHECKING:
    from plan_engine.generator.cli import GeneratorArgs, RoomSpec
    from plan_engine.generator.metrics import FloorMetrics


@dataclass
class FloorRoom:
    """A room assigned to a specific floor.

    Attributes:
        id: Unique room identifier (e.g., "master", "bed2", "bed3_cl").
        room_type: Canonical room type (e.g., "bedroom", "closet", "ldk").
        floor: Floor number (1 or 2).
        target_jo: User-specified target in tatami, or None for auto.
        min_width_mm: User-specified min width, or None for default.
        parent_id: Parent room ID for closets, or None.
        is_fixed: True for fixed-size rooms (wet, toilet, stair).
        fixed_w_mm: Fixed width for fixed-size rooms.
        fixed_d_mm: Fixed depth for fixed-size rooms.
    """

    id: str
    room_type: str
    floor: int
    target_jo: float | None = None
    min_width_mm: int | None = None
    parent_id: str | None = None
    is_fixed: bool = False
    fixed_w_mm: int | None = None
    fixed_d_mm: int | None = None


@dataclass
class FloorPlan:
    """Room assignment for a single floor.

    Attributes:
        floor: Floor number.
        rooms: List of rooms on this floor.
        wet_type: Wet module type ("standard" or "compact").
        has_stair: Whether this floor has a stair.
    """

    floor: int
    rooms: list[FloorRoom] = field(default_factory=list)
    wet_type: str = "standard"
    has_stair: bool = False


def _compute_f2_bedroom_capacity(
    metrics: FloorMetrics,
    stair_type: str,
) -> int:
    """Estimate how many bedrooms F2 can hold.

    Subtracts stair, toilet, and compact wet (worst-case saving) from
    total cells, then divides by a bedroom estimate (bed + closet).
    Uses lighter estimates since the solver handles exact placement.

    Returns:
        Maximum number of bedrooms for F2.
    """
    total = metrics.total_cells
    stair_cells = STAIR_CELLS_ESTIMATE.get(stair_type, 12)
    toilet_cells = ROOM_WEIGHT_CELLS["toilet"]
    # Use compact wet for capacity estimation (optimistic).
    wet_cells = ROOM_WEIGHT_CELLS["ws+shower"]
    hall_cells = ROOM_WEIGHT_CELLS["hall"]

    available = total - stair_cells - toilet_cells - wet_cells - hall_cells
    # Use a lighter per-bedroom estimate: ~5jo bed + ~1jo closet = 12 cells.
    bed_with_cl = 12
    master_with_cl = 14  # slightly larger
    if available < master_with_cl:
        return 0
    remaining = available - master_with_cl
    return 1 + max(0, remaining // bed_with_cl)


def _distribute_bedrooms(
    n_bedrooms: int,
    metrics: FloorMetrics,
    stair_type: str,
    floors: int,
) -> tuple[int, int]:
    """Distribute bedrooms between F1 and F2.

    Strategy: fill F2 first (up to capacity), overflow to F1.
    For 1F mode, all bedrooms go to F1.

    Returns:
        (f1_bed_count, f2_bed_count) tuple.
    """
    if floors == 1:
        return (n_bedrooms, 0)

    f2_cap = _compute_f2_bedroom_capacity(metrics, stair_type)
    f2_beds = min(n_bedrooms, f2_cap)
    f1_beds = n_bedrooms - f2_beds
    return (f1_beds, f2_beds)


def _make_fixed_room(
    room_id: str,
    room_type: str,
    floor: int,
) -> FloorRoom:
    """Create a fixed-size room (wet module or toilet)."""
    size = WET_FIXED_SIZES_MM.get(room_type)
    if size:
        return FloorRoom(
            id=room_id,
            room_type=room_type,
            floor=floor,
            is_fixed=True,
            fixed_w_mm=size[0],
            fixed_d_mm=size[1],
        )
    return FloorRoom(id=room_id, room_type=room_type, floor=floor)


def _build_floor_from_specs(
    floor_num: int,
    specs: list[RoomSpec],
    closets: str,
    has_stair: bool,
) -> FloorPlan:
    """Build a FloorPlan from user-provided room specs."""
    plan = FloorPlan(floor=floor_num, has_stair=has_stair)
    bed_index = 1 if floor_num == 1 else 2  # F2 beds start at 2 (master is special)

    for spec in specs:
        for _ in range(spec.count):
            room_type = spec.room_type

            # Determine room ID.
            if room_type == "master_bedroom":
                room_id = "master"
            elif room_type == "bedroom":
                room_id = f"bed{bed_index}"
                bed_index += 1
            elif room_type in ("washroom", "bath", "washstand", "shower", "toilet"):
                room_id = f"{room_type}{floor_num}"
            elif room_type == "ldk":
                room_id = "ldk"
            elif room_type == "entry":
                room_id = "entry"
            elif room_type == "hall":
                room_id = f"hall{floor_num}"
            elif room_type == "storage":
                room_id = f"storage{floor_num}"
            elif room_type == "wic":
                room_id = f"wic{floor_num}"
            elif room_type == "closet":
                room_id = f"cl{floor_num}_{bed_index}"
                bed_index += 1
            else:
                room_id = f"{room_type}{floor_num}"

            # Create the room.
            fixed_size = WET_FIXED_SIZES_MM.get(room_type)
            room = FloorRoom(
                id=room_id,
                room_type=room_type,
                floor=floor_num,
                target_jo=spec.target_jo,
                min_width_mm=spec.min_width_mm,
                is_fixed=fixed_size is not None,
                fixed_w_mm=fixed_size[0] if fixed_size else None,
                fixed_d_mm=fixed_size[1] if fixed_size else None,
            )
            plan.rooms.append(room)

            # Handle attachment (e.g., +wic, +cl).
            if spec.attachment:
                attach_type = spec.attachment
                attach_id = f"{room_id}_wic" if attach_type == "wic" else f"{room_id}_cl"
                attach_room = FloorRoom(
                    id=attach_id,
                    room_type=attach_type,
                    floor=floor_num,
                    target_jo=spec.attachment_target_jo,
                    parent_id=room_id,
                )
                plan.rooms.append(attach_room)

    return plan


def _build_auto_floor(
    floor_num: int,
    n_bedrooms: int,
    metrics: FloorMetrics,
    stair_type: str,
    closets: str,
    is_2f: bool,
) -> FloorPlan:
    """Build a FloorPlan automatically for the given floor."""
    has_stair = is_2f
    plan = FloorPlan(floor=floor_num, has_stair=has_stair)

    if floor_num == 1:
        # F1 always has: entry, hall, ldk.
        plan.rooms.append(FloorRoom(id="entry", room_type="entry", floor=1))
        plan.rooms.append(FloorRoom(id="hall1", room_type="hall", floor=1))
        plan.rooms.append(FloorRoom(id="ldk", room_type="ldk", floor=1))

        # F1 bedrooms (only in spillover case).
        for i in range(n_bedrooms):
            bed_id = f"bed{i + 1}"
            plan.rooms.append(FloorRoom(id=bed_id, room_type="bedroom", floor=1))
            if closets == "auto":
                cl_id = f"{bed_id}_cl"
                plan.rooms.append(
                    FloorRoom(
                        id=cl_id,
                        room_type="closet",
                        floor=1,
                        parent_id=bed_id,
                    )
                )

        # F1 wet: always standard (washroom + bath).
        plan.rooms.append(_make_fixed_room("toilet1", "toilet", 1))
        plan.rooms.append(_make_fixed_room("wash1", "washroom", 1))
        plan.rooms.append(_make_fixed_room("bath1", "bath", 1))

        # Storage.
        plan.rooms.append(FloorRoom(id="storage1", room_type="storage", floor=1))

    else:
        # F2: hall.
        plan.rooms.append(FloorRoom(id="hall2", room_type="hall", floor=2))

        # Master bedroom is always the first on F2.
        if n_bedrooms >= 1:
            plan.rooms.append(
                FloorRoom(id="master", room_type="master_bedroom", floor=2)
            )
            if closets == "auto":
                plan.rooms.append(
                    FloorRoom(
                        id="master_cl",
                        room_type="closet",
                        floor=2,
                        parent_id="master",
                    )
                )

        # Remaining bedrooms on F2.
        for i in range(1, n_bedrooms):
            bed_id = f"bed{i + 1}"
            plan.rooms.append(
                FloorRoom(id=bed_id, room_type="bedroom", floor=2)
            )
            if closets == "auto":
                cl_id = f"{bed_id}_cl"
                plan.rooms.append(
                    FloorRoom(
                        id=cl_id,
                        room_type="closet",
                        floor=2,
                        parent_id=bed_id,
                    )
                )

        # F2 wet: decided later by wet selection stage.
        plan.rooms.append(_make_fixed_room("toilet2", "toilet", 2))
        # Placeholder standard wet — may be replaced by compact.
        plan.rooms.append(_make_fixed_room("wash2", "washroom", 2))
        plan.rooms.append(_make_fixed_room("bath2", "bath", 2))

    return plan


def _compute_target_density(
    plan: FloorPlan,
    metrics: FloorMetrics,
    stair_type: str,
) -> float:
    """Estimate target density for a floor plan.

    density = (fixed_cells + variable_room_estimate) / total_cells

    For estimation purposes, variable rooms use the midpoint of their
    min/max range from ROOM_WEIGHT_CELLS, or a rough cell estimate.
    """
    total = metrics.total_cells
    if total == 0:
        return 1.0

    fixed_cells = 0
    variable_jo = 0.0

    # Stair cells.
    if plan.has_stair:
        fixed_cells += STAIR_CELLS_ESTIMATE.get(stair_type, 12)

    for room in plan.rooms:
        if room.is_fixed:
            w = room.fixed_w_mm or 910
            d = room.fixed_d_mm or 910
            fixed_cells += (w // 910) * (d // 910)
        else:
            profile = ROOM_PROFILE.get(room.room_type)
            if profile:
                mid = (profile.min_jo + profile.max_jo) / 2
                variable_jo += room.target_jo if room.target_jo else mid
            else:
                variable_jo += 3.0  # fallback estimate

    # Convert variable_jo to cells: 1 jo = 2 cells (910x1820 = 2 x 910²).
    variable_cells = variable_jo * 2
    return (fixed_cells + variable_cells) / total


def select_wet_modules(
    plan: FloorPlan,
    metrics: FloorMetrics,
    stair_type: str,
) -> FloorPlan:
    """Stage 3: Auto-select wet module type based on density.

    If target density > 85% with standard wet, replace with compact.
    Only applies to auto-generated wet (not user-specified).
    """
    density = _compute_target_density(plan, metrics, stair_type)

    if density > COMPACT_WET_DENSITY_THRESHOLD:
        # Replace standard wet with compact.
        plan.wet_type = "compact"
        new_rooms: list[FloorRoom] = []
        for room in plan.rooms:
            if room.room_type == "washroom":
                new_rooms.append(
                    _make_fixed_room(
                        room.id.replace("wash", "washstand"),
                        "washstand",
                        room.floor,
                    )
                )
            elif room.room_type == "bath":
                new_rooms.append(
                    _make_fixed_room(
                        room.id.replace("bath", "shower"),
                        "shower",
                        room.floor,
                    )
                )
            else:
                new_rooms.append(room)
        plan.rooms = new_rooms

    return plan


def _has_user_wet(specs: list[RoomSpec]) -> bool:
    """Check if user explicitly specified wet rooms."""
    wet_types = {"washroom", "bath", "washstand", "shower"}
    return any(s.room_type in wet_types for s in specs)


def distribute_rooms(
    args: GeneratorArgs,
    metrics: FloorMetrics,
) -> list[FloorPlan]:
    """Main distribution entry point: produce per-floor room lists.

    Handles both --rooms shorthand and --f1/--f2 override modes.

    Returns:
        List of FloorPlan objects (one per floor).
    """
    is_2f = args.floors >= 2
    plans: list[FloorPlan] = []

    if args.f1_specs is not None:
        # User specified F1 explicitly.
        f1 = _build_floor_from_specs(1, args.f1_specs, args.closets, is_2f)
        plans.append(f1)
    elif args.n_ldk is not None:
        # Use shorthand distribution.
        f1_beds, _ = _distribute_bedrooms(
            args.n_ldk, metrics, args.stair_type, args.floors
        )
        f1 = _build_auto_floor(1, f1_beds, metrics, args.stair_type, args.closets, is_2f)
        plans.append(f1)
    else:
        # No room info — build minimal F1.
        f1 = _build_auto_floor(1, 0, metrics, args.stair_type, args.closets, is_2f)
        plans.append(f1)

    if is_2f:
        if args.f2_specs is not None:
            f2 = _build_floor_from_specs(2, args.f2_specs, args.closets, True)
            plans.append(f2)
            # Auto wet selection only if user didn't specify wet rooms.
            if not _has_user_wet(args.f2_specs):
                select_wet_modules(f2, metrics, args.stair_type)
        elif args.n_ldk is not None:
            _, f2_beds = _distribute_bedrooms(
                args.n_ldk, metrics, args.stair_type, args.floors
            )
            f2 = _build_auto_floor(
                2, f2_beds, metrics, args.stair_type, args.closets, is_2f
            )
            plans.append(f2)
            # Auto wet selection for F2.
            select_wet_modules(f2, metrics, args.stair_type)
        else:
            f2 = _build_auto_floor(2, 0, metrics, args.stair_type, args.closets, is_2f)
            plans.append(f2)
            select_wet_modules(f2, metrics, args.stair_type)

    return plans
