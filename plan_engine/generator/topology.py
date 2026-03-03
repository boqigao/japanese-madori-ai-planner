"""Stage 5: Automatic topology generation from room lists."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from plan_engine.generator.profiles import TOPOLOGY_RULES

if TYPE_CHECKING:
    from plan_engine.generator.distribute import FloorPlan


@dataclass(frozen=True)
class AdjEdge:
    """A single adjacency edge in the topology.

    Attributes:
        left: Left room ID.
        right: Right room ID.
        strength: Edge strength ("required" or "preferred").
    """

    left: str
    right: str
    strength: str


def generate_topology(plan: FloorPlan) -> list[AdjEdge]:
    """Generate topology adjacency edges for a floor plan.

    Applies TOPOLOGY_RULES template to the rooms present on this floor.
    Handles:
        - "always": Always add the edge if both rooms exist.
        - "if_exists": Add if the right room type exists.
        - "per_bedroom": Expand for each bedroom on the floor.
        - "if_wic": Add if a WIC attachment exists for the master.

    Returns:
        List of AdjEdge objects.
    """
    edges: list[AdjEdge] = []

    # Build lookup: room_type → list of room IDs.
    type_to_ids: dict[str, list[str]] = {}
    for room in plan.rooms:
        type_to_ids.setdefault(room.room_type, []).append(room.id)

    # Build parent_id → closet_id lookup (closets only, not WIC).
    parent_to_closet: dict[str, str] = {}
    for room in plan.rooms:
        if room.parent_id and room.room_type == "closet":
            parent_to_closet[room.parent_id] = room.id

    # Find stair ID if present.
    stair_id = "stair" if plan.has_stair else None

    # Find bedrooms (for per_bedroom expansion).
    bedrooms = [
        r for r in plan.rooms
        if r.room_type in ("bedroom", "master_bedroom")
    ]

    # Find master and WIC.
    master_ids = type_to_ids.get("master_bedroom", [])
    wic_ids = type_to_ids.get("wic", [])

    for condition, left_tpl, right_tpl, strength in TOPOLOGY_RULES:
        if condition in {"always", "if_exists"}:
            left_id = _resolve_id(left_tpl, type_to_ids, stair_id)
            right_id = _resolve_id(right_tpl, type_to_ids, stair_id)
            if left_id and right_id:
                edges.append(AdjEdge(left=left_id, right=right_id, strength=strength))

        elif condition == "per_bedroom":
            for bed in bedrooms:
                left_id = bed.id if left_tpl == "{bed}" else _resolve_id(left_tpl, type_to_ids, stair_id)

                if right_tpl == "{bed}":
                    right_id = bed.id
                elif right_tpl == "{bed_cl}":
                    right_id = parent_to_closet.get(bed.id)
                else:
                    right_id = _resolve_id(right_tpl, type_to_ids, stair_id)

                if left_id and right_id:
                    edges.append(
                        AdjEdge(left=left_id, right=right_id, strength=strength)
                    )

        elif condition == "if_wic":
            # WIC edges: master → wic (preferred).
            # Build wic lookup from parent_id.
            parent_to_wic: dict[str, str] = {}
            for room in plan.rooms:
                if room.parent_id and room.room_type == "wic":
                    parent_to_wic[room.parent_id] = room.id

            for master_id in master_ids:
                wic_id = parent_to_wic.get(master_id)
                if wic_id:
                    edges.append(
                        AdjEdge(left=master_id, right=wic_id, strength=strength)
                    )
                # Also check for standalone WICs.
                for wid in wic_ids:
                    if wid not in parent_to_wic.values():
                        edges.append(
                            AdjEdge(left=master_id, right=wid, strength=strength)
                        )

    return edges


def _resolve_id(
    template: str,
    type_to_ids: dict[str, list[str]],
    stair_id: str | None,
) -> str | None:
    """Resolve a template name to a room ID.

    Returns the first matching room ID, or None if not found.
    """
    if template == "stair":
        return stair_id

    # Direct room type lookup.
    ids = type_to_ids.get(template, [])
    if ids:
        return ids[0]

    return None
