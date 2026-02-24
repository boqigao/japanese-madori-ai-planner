from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StairPortal:
    """Identifies which stair component and edge connects to the hall."""

    component_index: int
    edge: str  # left | right | top | bottom


def ordered_floor_ids(ids: set[str] | list[str]) -> list[str]:
    """Sort floor IDs numerically then lexicographically."""

    def key(value: str) -> tuple[int, str]:
        digits = "".join(ch for ch in value if ch.isdigit())
        return (int(digits) if digits else 10_000, value)

    return sorted(ids, key=key)


def stair_portal_for_floor(
    stair_type: str,
    floor_index: int,
    floor_count: int,
    component_count: int,
) -> StairPortal:
    """Determine the stair portal (component index and edge) for a given floor.

    Args:
        stair_type: Type of stair (e.g. "straight", "L_landing").
        floor_index: Zero-based index of the floor being queried.
        floor_count: Total number of floors connected by the stair.
        component_count: Number of rectangular components in the stair geometry.

    Returns:
        A StairPortal indicating which component edge faces the hall on the
        requested floor.

    Raises:
        ValueError: If floor_count exceeds 2 or floor_index is out of range.
    """
    if floor_count > 2:
        raise ValueError("deterministic stair portal mapping currently supports up to 2 floors")
    if floor_index < 0 or floor_index >= floor_count:
        raise ValueError(f"floor_index out of range: {floor_index}/{floor_count}")

    if stair_type == "straight" or component_count <= 1:
        return StairPortal(component_index=0, edge="top" if floor_index == 0 else "bottom")

    if stair_type != "L_landing" or component_count < 3:
        return StairPortal(component_index=0, edge="left")

    if floor_index == 0:
        # Lower floor: access stair run start.
        return StairPortal(component_index=0, edge="left")
    # Upper floor: access final run end.
    return StairPortal(component_index=2, edge="bottom")

