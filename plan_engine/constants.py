from __future__ import annotations

import math

MINOR_GRID_MM = 455
MAJOR_GRID_MM = 910
TATAMI_MM2 = 1_620_000

MAJOR_ROOM_TYPES = {"ldk", "bedroom", "master_bedroom"}
WET_SPACE_TYPES = {"toilet", "wc", "washroom", "bath"}

WET_MODULE_SIZES_MM: dict[str, tuple[int, int]] = {
    "toilet": (910, 1820),
    "wc": (910, 1820),
    "washroom": (1820, 1820),
    "bath": (1820, 1820),
}


def ceil_to_grid(value: int, grid: int) -> int:
    return int(math.ceil(value / grid) * grid)


def mm_to_cells(mm_value: int, minor_grid: int) -> int:
    if mm_value % minor_grid != 0:
        raise ValueError(f"value {mm_value} must align to {minor_grid}mm grid")
    return mm_value // minor_grid


def cells_to_mm(cells: int, minor_grid: int) -> int:
    return cells * minor_grid


def tatami_to_cells(tatami: float, minor_grid: int) -> int:
    cell_area = minor_grid * minor_grid
    return int(math.ceil((tatami * TATAMI_MM2) / cell_area))

