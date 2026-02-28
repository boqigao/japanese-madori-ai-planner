from __future__ import annotations

import math

MINOR_GRID_MM = 455
MAJOR_GRID_MM = 910
TATAMI_MM2 = 1_620_000

MAJOR_ROOM_TYPES = {"ldk", "bedroom", "master_bedroom"}
WET_SPACE_TYPES = {"toilet", "wc", "washroom", "bath"}
OUTDOOR_SPACE_TYPES = {"balcony", "veranda"}
STAIR_TYPES = {"straight", "L_landing"}
EDGE_NAMES = {"left", "right", "top", "bottom"}

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
