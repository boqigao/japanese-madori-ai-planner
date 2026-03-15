"""Room profiles, weights, and configuration constants."""

from __future__ import annotations

from dataclasses import dataclass

TATAMI_MM2 = 1_620_000


@dataclass(frozen=True)
class RoomProfile:
    """Area allocation profile for a variable-size room type.

    Attributes:
        weight: Proportional share weight for area distribution.
        min_jo: Minimum target in tatami (safety floor).
        max_jo: Maximum target in tatami (safety ceiling).
    """

    weight: float
    min_jo: float
    max_jo: float


ROOM_PROFILE: dict[str, RoomProfile] = {
    "ldk": RoomProfile(weight=5.0, min_jo=12.0, max_jo=28.0),
    "master_bedroom": RoomProfile(weight=3.0, min_jo=6.0, max_jo=14.0),
    "bedroom": RoomProfile(weight=2.0, min_jo=4.5, max_jo=10.0),
    "hall": RoomProfile(weight=1.5, min_jo=3.0, max_jo=7.0),
    "entry": RoomProfile(weight=0.8, min_jo=1.5, max_jo=3.5),
    "storage": RoomProfile(weight=1.0, min_jo=1.5, max_jo=5.0),
    "closet": RoomProfile(weight=0.4, min_jo=0.75, max_jo=2.0),
    "wic": RoomProfile(weight=0.8, min_jo=1.5, max_jo=3.5),
}

# Per-room cell weight for F2 capacity estimation (1 cell = 910x910mm, 1 jo = 2 cells).
# Includes closet overhead where applicable.
ROOM_WEIGHT_CELLS: dict[str, int] = {
    "master_bedroom": 18,  # ~8jo + 1jo closet = 18 cells
    "bedroom": 14,  # ~6jo + 1jo closet = 14 cells
    "hall": 8,  # ~4jo = 8 cells
    "toilet": 2,  # fixed 910x1820 = 2 cells
    "wash+bath": 8,  # fixed (1820x1820)x2 = 8 cells
    "ws+shower": 3,  # fixed 910x910 + 910x1365 ≈ 3 cells
}

# Fixed wet module sizes in mm (width, depth) — from constants.py.
WET_FIXED_SIZES_MM: dict[str, tuple[int, int]] = {
    "toilet": (910, 1820),
    "washroom": (1820, 1820),
    "bath": (1820, 1820),
    "washstand": (910, 910),
    "shower": (910, 1365),
}

# Density threshold: if target density > this with standard wet, switch to compact.
COMPACT_WET_DENSITY_THRESHOLD = 0.85

# Min_width defaults by room type (mm).
MIN_WIDTH_DEFAULTS: dict[str, int] = {
    "ldk": 1820,
    "master_bedroom": 1820,
    "bedroom": 1820,
    "hall": 910,
    "entry": 1365,
    "storage": 910,
    "closet": 910,
    "wic": 1820,
}

# Topology rule templates.
# Conditions: "always", "if_exists", "per_bedroom", "if_wic"
TOPOLOGY_RULES: list[tuple[str, str, str, str]] = [
    ("always", "entry", "hall", "required"),
    ("always", "hall", "stair", "required"),
    ("always", "hall", "ldk", "required"),
    ("if_exists", "hall", "toilet", "required"),
    ("if_exists", "hall", "washroom", "required"),
    ("if_exists", "hall", "washstand", "required"),
    ("if_exists", "washroom", "bath", "required"),
    ("if_exists", "washstand", "shower", "required"),
    ("if_exists", "hall", "storage", "required"),
    ("per_bedroom", "hall", "{bed}", "required"),
    ("per_bedroom", "{bed}", "{bed_cl}", "required"),
    ("if_wic", "{master}", "{wic}", "preferred"),
]

# Default stair configuration.
DEFAULT_STAIR_TYPE = "U_turn"


def select_stair_type(envelope_width_mm: int) -> str:
    """Select optimal stair type based on lot width.

    Thresholds (based on stair footprint + hall + room fit):
        <=6370mm (14 cells): straight (2-cell width fits beside hall)
        <=7735mm (15-17 cells): L_landing (5-cell footprint fits)
        >=8190mm (18+ cells): U_turn (preferred when space allows)
    """
    if envelope_width_mm <= 6370:
        return "straight"
    elif envelope_width_mm <= 7735:
        return "L_landing"
    else:
        return "U_turn"
DEFAULT_STAIR_WIDTH_MM = 910
DEFAULT_FLOOR_HEIGHT_MM = 2730
DEFAULT_RISER_PREF_MM = 230
DEFAULT_TREAD_PREF_MM = 210

# Stair cell consumption estimates by type.
STAIR_CELLS_ESTIMATE: dict[str, int] = {
    "straight": 8,
    "L_landing": 12,
    "U_turn": 12,
}
