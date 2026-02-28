from __future__ import annotations

from typing import TYPE_CHECKING

from plan_engine.constants import mm_to_cells, tatami_to_cells

if TYPE_CHECKING:
    from plan_engine.models import SpaceSpec

DEFAULT_MIN_TATAMI_BY_TYPE: dict[str, float] = {
    "entry": 2.0,
    "hall": 2.0,
    "ldk": 12.0,
    "bedroom": 6.0,
}

SHORTFALL_WEIGHT_BY_TYPE: dict[str, int] = {
    "hall": 48,
    "bedroom": 36,
    "master_bedroom": 36,
    "ldk": 34,
    "entry": 30,
}

OVERSHOOT_WEIGHT_BY_TYPE: dict[str, int] = {
    "hall": 82,
    "entry": 38,
    "bedroom": 42,
    "master_bedroom": 48,
    "ldk": 52,
    "storage": 44,
}

MIN_WIDTH_CELLS_BY_TYPE: dict[str, int] = {
    "ldk": 4,
    "bedroom": 3,
    "master_bedroom": 3,
    "entry": 3,
    "hall": 2,
}

COMPONENT_CAP_BY_TYPE: dict[str, int] = {
    "ldk": 2,
    "hall": 4,
}

SOUTH_PREFERENCE_WEIGHT_BY_TYPE: dict[str, int] = {
    "ldk": 72,
    "master_bedroom": 52,
    "bedroom": 44,
}

NORTH_PREFERENCE_WEIGHT_BY_TYPE: dict[str, int] = {
    "washroom": 30,
    "bath": 30,
    "toilet": 26,
    "wc": 26,
    "storage": 22,
}

MAX_AREA_TARGET_MULTIPLIER_BY_TYPE: dict[str, float] = {
    "entry": 1.5,
    "hall": 1.5,
    "master_bedroom": 1.5,
    "bedroom": 1.5,
    "ldk": 1.45,
    "storage": 1.45,
}

MAX_AREA_DEFAULT_TATAMI_BY_TYPE: dict[str, float] = {
    "entry": 4.5,
    "hall": 9.0,
    "master_bedroom": 12.0,
    "bedroom": 10.0,
    "ldk": 16.0,
    "storage": 8.0,
}

ENTRY_MIN_AREA_DEFAULT_TATAMI = 3.0
ENTRY_HARD_MAX_TATAMI = 2.5
TARGET_TO_MIN_RATIO = 0.70


def _component_count(space: SpaceSpec) -> int:
    """Determine the number of rectangle components a space can use."""
    allow_l2 = "L2" in space.shape.allow
    allow_rect = "rect" in space.shape.allow
    if not allow_l2 or allow_rect:
        return 1
    cap = COMPONENT_CAP_BY_TYPE.get(space.type)
    if cap is None or space.shape.rect_components_max < 2:
        return 1
    return min(cap, max(2, space.shape.rect_components_max))


def _min_area_cells(space: SpaceSpec, minor_grid: int) -> int:
    """Calculate the minimum area in cells for a space.

    Priority order:
    1) Explicit ``min_tatami`` from spec (hard requirement).
    2) ``target_tatami`` scaled by ``TARGET_TO_MIN_RATIO`` to keep target as a
       soft goal while preserving area shrink flexibility.
    3) Type default minimum.
    """
    if space.area.min_tatami is not None:
        return tatami_to_cells(space.area.min_tatami, minor_grid)
    if space.area.target_tatami is not None:
        return tatami_to_cells(space.area.target_tatami * TARGET_TO_MIN_RATIO, minor_grid)
    default_tatami = DEFAULT_MIN_TATAMI_BY_TYPE.get(space.type)
    if default_tatami is not None:
        return tatami_to_cells(default_tatami, minor_grid)
    return 4


def _target_area_cells(space: SpaceSpec, minor_grid: int) -> int | None:
    """Get the target area in cells if specified in the space spec."""
    if space.area.target_tatami is None:
        return None
    return tatami_to_cells(space.area.target_tatami, minor_grid)


def _shortfall_weight(space_type: str) -> int:
    """Get the penalty weight for area undershooting by space type."""
    return SHORTFALL_WEIGHT_BY_TYPE.get(space_type, 28)


def _overshoot_weight(space_type: str) -> int:
    """Get the penalty weight for area overshooting by space type."""
    return OVERSHOOT_WEIGHT_BY_TYPE.get(space_type, 9)


def _south_preference_weight(space_type: str) -> int:
    """Return orientation penalty weight for missing south-edge touch.

    Args:
        space_type: Canonical room type.

    Returns:
        Positive weight when the room should prefer the south facade,
        otherwise ``0``.
    """
    return SOUTH_PREFERENCE_WEIGHT_BY_TYPE.get(space_type, 0)


def _north_preference_weight(space_type: str) -> int:
    """Return orientation penalty weight for missing north-edge touch.

    Args:
        space_type: Canonical room type.

    Returns:
        Positive weight when the room should prefer the north facade,
        otherwise ``0``.
    """
    return NORTH_PREFERENCE_WEIGHT_BY_TYPE.get(space_type, 0)


def _max_area_cells(space: SpaceSpec, minor_grid: int) -> int | None:
    """Calculate the maximum allowed area in cells for a space.

    Notes:
        Entry is capped by a hard upper bound (``ENTRY_HARD_MAX_TATAMI``)
        regardless of target area, to keep genkan size within livable norms.
    """
    if space.type == "entry":
        return tatami_to_cells(ENTRY_HARD_MAX_TATAMI, minor_grid)

    multiplier = MAX_AREA_TARGET_MULTIPLIER_BY_TYPE.get(space.type)
    if multiplier is not None and space.area.target_tatami is not None:
        return tatami_to_cells(space.area.target_tatami * multiplier, minor_grid)

    if space.type == "entry" and space.area.min_tatami is not None:
        return tatami_to_cells(
            max(ENTRY_MIN_AREA_DEFAULT_TATAMI, space.area.min_tatami * 1.5),
            minor_grid,
        )

    default_tatami = MAX_AREA_DEFAULT_TATAMI_BY_TYPE.get(space.type)
    if default_tatami is None:
        return None
    return tatami_to_cells(default_tatami, minor_grid)


def _min_width_cells(space: SpaceSpec, minor_grid: int) -> int:
    """Calculate the minimum width in cells for a space."""
    if space.size_constraints.min_width is not None:
        return mm_to_cells(space.size_constraints.min_width, minor_grid)
    return MIN_WIDTH_CELLS_BY_TYPE.get(space.type, 1)
