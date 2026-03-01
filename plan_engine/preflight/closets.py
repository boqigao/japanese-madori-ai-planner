from __future__ import annotations

from typing import TYPE_CHECKING

from plan_engine.constants import (
    BEDROOM_SPACE_TYPES,
    CIRCULATION_SPACE_TYPES,
    WALK_IN_CLOSET_SPACE_TYPES,
)
from plan_engine.preflight.topology import _edge_ids
from plan_engine.solver.rect_var import _find_global_stair

if TYPE_CHECKING:
    from plan_engine.models import PlanSpec, ValidationReport


def _check_reference_consistency(spec: PlanSpec, report: ValidationReport) -> None:
    """Validate adjacency and stair references point to declared floor entities."""
    global_stair = _find_global_stair(spec)
    stair_id = global_stair.id if global_stair is not None else None

    for floor_id, floor in spec.floors.items():
        space_ids = {space.id for space in floor.spaces}
        floor_stair_id = floor.core.stair.id if floor.core.stair is not None else stair_id
        valid_ids = set(space_ids)
        if floor_stair_id is not None:
            valid_ids.add(floor_stair_id)

        for edge in floor.topology.adjacency:
            left_id, right_id = _edge_ids(edge)
            if left_id not in valid_ids:
                report.errors.append(f"preflight: {floor_id} adjacency references unknown id '{left_id}'")
            if right_id not in valid_ids:
                report.errors.append(f"preflight: {floor_id} adjacency references unknown id '{right_id}'")

    if global_stair is None:
        return
    for floor_id, hall_id in global_stair.connects.items():
        if floor_id not in spec.floors:
            report.errors.append(f"preflight: stair connects references unknown floor '{floor_id}'")
            continue
        hall_map = {space.id: space.type for space in spec.floors[floor_id].spaces}
        if hall_id not in hall_map:
            report.errors.append(f"preflight: stair connects references unknown space '{hall_id}' on {floor_id}")
            continue
        if hall_map[hall_id] != "hall":
            report.errors.append(f"preflight: stair connect target '{hall_id}' on {floor_id} must be type hall")


def _check_closet_semantics(spec: PlanSpec, floor_id: str, report: ValidationReport) -> None:
    """Validate embedded-closet metadata and WIC parent/access declarations.

    Args:
        spec: Parsed plan specification.
        floor_id: Floor identifier to validate.
        report: Mutable preflight report.

    Returns:
        None.
    """
    floor = spec.floors[floor_id]
    space_type_by_id = {space.id: space.type for space in floor.spaces}
    if not floor.embedded_closets and not any(space.type in WALK_IN_CLOSET_SPACE_TYPES for space in floor.spaces):
        return

    global_stair = _find_global_stair(spec)
    stair_id = floor.core.stair.id if floor.core.stair is not None else global_stair.id if global_stair else None
    floor_has_stair = floor.core.stair is not None or (global_stair is not None and floor_id in global_stair.connects)

    circulation_ids = {
        space_id
        for space_id, space_type in space_type_by_id.items()
        if space_type in CIRCULATION_SPACE_TYPES
    }
    if floor_has_stair and stair_id is not None:
        circulation_ids.add(stair_id)

    neighbor_map: dict[str, set[str]] = {space.id: set() for space in floor.spaces}
    for edge in floor.topology.adjacency:
        left_id, right_id = _edge_ids(edge)
        neighbor_map.setdefault(left_id, set()).add(right_id)
        neighbor_map.setdefault(right_id, set()).add(left_id)

    for closet in floor.embedded_closets:
        parent_type = space_type_by_id.get(closet.parent_id)
        if parent_type is None:
            report.errors.append(
                f"preflight: {floor_id}:{closet.id} references unknown parent_id '{closet.parent_id}'"
            )
            continue
        if parent_type not in BEDROOM_SPACE_TYPES:
            report.errors.append(
                f"preflight: {floor_id}:{closet.id} closet parent '{closet.parent_id}' must be bedroom/master_bedroom"
            )

    for space in floor.spaces:
        if space.type not in WALK_IN_CLOSET_SPACE_TYPES:
            continue
        if space.parent_id is None:
            report.errors.append(f"preflight: {floor_id}:{space.id} wic requires parent_id")
            continue
        parent_type = space_type_by_id.get(space.parent_id)
        if parent_type is None:
            report.errors.append(
                f"preflight: {floor_id}:{space.id} references unknown parent_id '{space.parent_id}'"
            )
            continue
        if space.type in WALK_IN_CLOSET_SPACE_TYPES and parent_type not in BEDROOM_SPACE_TYPES:
            report.errors.append(
                f"preflight: {floor_id}:{space.id} wic parent '{space.parent_id}' must be bedroom/master_bedroom"
            )

        neighbors = neighbor_map.get(space.id, set())
        if space.parent_id not in neighbors:
            report.errors.append(
                f"preflight: {floor_id}:{space.id} wic must declare topology adjacency to parent '{space.parent_id}'"
            )
            report.suggestions.append(
                f"Add topology adjacency like [{space.id}, {space.parent_id}, required] on {floor_id}."
            )

        if space.type in WALK_IN_CLOSET_SPACE_TYPES:
            allowed_access = circulation_ids.union({space.parent_id})
            if not any(neighbor in allowed_access for neighbor in neighbors):
                report.errors.append(
                    f"preflight: {floor_id}:{space.id} has no candidate access declaration "
                    "(expected parent/hall/entry/stair edge)"
                )
                report.suggestions.append(
                    f"Add topology adjacency from {space.id} to {space.parent_id} or hall/entry/stair on {floor_id}."
                )


def _warn_bedrooms_without_closet(spec: PlanSpec, floor_id: str, report: ValidationReport) -> None:
    """Warn when a bedroom has no associated closet or walk-in closet.

    Args:
        spec: Parsed plan specification.
        floor_id: Floor identifier to inspect.
        report: Mutable report receiving warnings/suggestions.

    Returns:
        None.
    """
    floor = spec.floors[floor_id]
    bedroom_ids = {space.id for space in floor.spaces if space.type in BEDROOM_SPACE_TYPES}
    closet_parent_ids = {
        space.parent_id
        for space in floor.spaces
        if space.type in WALK_IN_CLOSET_SPACE_TYPES and space.parent_id is not None
    }
    closet_parent_ids.update(closet.parent_id for closet in floor.embedded_closets)
    for bedroom_id in sorted(bedroom_ids):
        if bedroom_id in closet_parent_ids:
            continue
        report.warnings.append(
            f"preflight: {floor_id}:{bedroom_id} has no associated closet or WIC"
        )
        report.suggestions.append(
            f"Add embedded closet or WIC for {floor_id}:{bedroom_id} "
            f"(for example under bedroom '{bedroom_id}': closet: {{id: {bedroom_id}_cl}})."
        )
