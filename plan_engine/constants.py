from __future__ import annotations

import math

MINOR_GRID_MM = 455
MAJOR_GRID_MM = 910
TATAMI_MM2 = 1_620_000

MAJOR_ROOM_TYPES = {"ldk", "bedroom", "master_bedroom"}
WET_SPACE_TYPES = {"toilet", "wc", "washroom", "bath"}
OUTDOOR_SPACE_TYPES = {"balcony", "veranda"}
EMBEDDED_CLOSET_SPACE_TYPES = {"closet"}
CLOSET_SPACE_TYPES = {"closet"}
WALK_IN_CLOSET_SPACE_TYPES = {"wic"}
STAIR_TYPES = {"straight", "L_landing", "U_turn"}
BEDROOM_SPACE_TYPES = frozenset({"bedroom", "master_bedroom"})
TOILET_SPACE_TYPES = frozenset({"toilet", "wc"})
WET_CORE_SPACE_TYPES = frozenset({"washroom", "bath"})
CIRCULATION_SPACE_TYPES = frozenset({"hall", "entry"})
EDGE_NAMES = {"left", "right", "top", "bottom"}
WINDOW_SPACE_TYPES = {"ldk", "bedroom", "master_bedroom", "entry"}

WET_MODULE_SIZES_MM: dict[str, tuple[int, int]] = {
    "toilet": (910, 1820),
    "wc": (910, 1820),
    "washroom": (1820, 1820),
    "bath": (1820, 1820),
}


def is_outdoor_space_type(space_type: str) -> bool:
    """Return True when ``space_type`` is classified as outdoor."""
    return space_type in OUTDOOR_SPACE_TYPES


def is_indoor_space_type(space_type: str) -> bool:
    """Return True when ``space_type`` is classified as indoor."""
    return space_type not in OUTDOOR_SPACE_TYPES


def is_closet_space_type(space_type: str) -> bool:
    """Return True when ``space_type`` is a closet-like space token."""
    return space_type in CLOSET_SPACE_TYPES


def ceil_to_grid(value: int, grid: int) -> int:
    """Round up *value* to the nearest multiple of *grid*."""
    return int(math.ceil(value / grid) * grid)


def mm_to_cells(mm_value: int, minor_grid: int) -> int:
    """Convert millimeters to grid cell count, raising ValueError if not aligned."""
    if mm_value % minor_grid != 0:
        raise ValueError(f"value {mm_value} must align to {minor_grid}mm grid")
    return mm_value // minor_grid


def cells_to_mm(cells: int, minor_grid: int) -> int:
    """Convert grid cell count back to millimeters."""
    return cells * minor_grid


def tatami_to_cells(tatami: float, minor_grid: int) -> int:
    """Convert tatami area to minimum cell count (rounded up)."""
    cell_area = minor_grid * minor_grid
    return math.ceil((tatami * TATAMI_MM2) / cell_area)


def should_draw_interior_door(left_type: str, right_type: str) -> bool:
    """Decide whether a topology edge between two space types warrants an interior door.

    Args:
        left_type: Space type on one side of the shared boundary.
        right_type: Space type on the other side of the shared boundary.

    Returns:
        ``True`` if a door should be placed, otherwise ``False``.
        Suppressed edges: outdoor-to-outdoor, closet edges, bedroom-to-bedroom,
        and bath-to-non-washroom.
    """
    types = {left_type, right_type}
    if types.issubset({"balcony", "veranda"}):
        return False
    if types.intersection({"closet"}):
        return False
    if left_type in BEDROOM_SPACE_TYPES and right_type in BEDROOM_SPACE_TYPES:
        return False
    return not ("bath" in types and "washroom" not in types)
