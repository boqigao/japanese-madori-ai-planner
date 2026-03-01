from __future__ import annotations

from plan_engine.constants import CLOSET_SPACE_TYPES, WALK_IN_CLOSET_SPACE_TYPES
from plan_engine.models import AreaConstraint, EmbeddedClosetSpec, SpaceSpec


def _parse_embedded_closets(
    raw_parent_space: dict[str, object],
    parent_space: SpaceSpec,
    minor: int,
) -> tuple[list[EmbeddedClosetSpec], list[SpaceSpec]]:
    """Parse embedded closet declarations under one parent space entry.

    Supported input forms:
        - ``closet: { ... }`` (single declaration)
        - ``closets: [ { ... }, ... ]`` (multiple declarations)

    Embedded closet entries are converted to ``EmbeddedClosetSpec`` metadata.
    Embedded WIC entries are kept as independent ``SpaceSpec`` objects with
    ``parent_id`` set to ``parent_space.id``.

    Args:
        raw_parent_space: Raw YAML mapping for the parent room.
        parent_space: Parsed parent space object.
        minor: Minor grid size in mm.

    Returns:
        Tuple ``(embedded_closets, embedded_wics)``.

    Raises:
        ValueError: If embedded closet declarations are malformed.
    """
    from plan_engine.dsl import _parse_space

    embedded_raw: list[dict[str, object]] = []
    single = raw_parent_space.get("closet")
    if single is not None:
        if not isinstance(single, dict):
            raise ValueError(f"embedded closet for '{parent_space.id}' must be a mapping")
        embedded_raw.append(single)
    multi = raw_parent_space.get("closets")
    if multi is not None:
        if not isinstance(multi, list):
            raise ValueError(f"embedded closets for '{parent_space.id}' must be a list")
        for idx, item in enumerate(multi):
            if not isinstance(item, dict):
                raise ValueError(f"embedded closets[{idx}] for '{parent_space.id}' must be a mapping")
            embedded_raw.append(item)
    if not embedded_raw:
        return [], []

    parsed_embedded: list[EmbeddedClosetSpec] = []
    parsed_wics: list[SpaceSpec] = []
    for idx, closet_raw in enumerate(embedded_raw, start=1):
        closet_payload = dict(closet_raw)
        closet_type = str(closet_payload.get("type", "closet"))
        if closet_type not in (CLOSET_SPACE_TYPES | WALK_IN_CLOSET_SPACE_TYPES):
            raise ValueError(
                f"embedded closet for '{parent_space.id}' must use type in "
                f"{sorted(CLOSET_SPACE_TYPES | WALK_IN_CLOSET_SPACE_TYPES)}"
            )
        closet_payload.setdefault("id", f"{parent_space.id}_{closet_type}{idx}")
        closet_payload["id"] = str(closet_payload["id"])
        closet_payload["type"] = closet_type
        closet_payload["parent_id"] = parent_space.id

        if closet_type in WALK_IN_CLOSET_SPACE_TYPES:
            parsed_wics.append(_parse_space(closet_payload, minor))
            continue
        parsed_embedded.append(_parse_embedded_closet_spec(closet_payload, parent_space.id, minor))
    return parsed_embedded, parsed_wics


def _parse_embedded_closet_spec(
    closet_payload: dict[str, object],
    parent_id: str,
    minor: int,
) -> EmbeddedClosetSpec:
    """Parse one embedded closet payload into immutable closet metadata.

    Args:
        closet_payload: Raw closet mapping with normalized ``id``/``type`` keys.
            ``depth_mm`` is read directly, or from ``size_constraints.min_width``
            for backward compatibility.
        parent_id: Host room identifier.
        minor: Minor grid size used for optional depth alignment validation.

    Returns:
        Parsed embedded closet metadata.

    Raises:
        ValueError: If ``depth_mm`` is not minor-grid aligned.
    """
    area_raw = closet_payload.get("area")
    area = AreaConstraint()
    if isinstance(area_raw, dict):
        min_tatami = area_raw.get("min_tatami")
        target_tatami = area_raw.get("target_tatami")
        area = AreaConstraint(
            min_tatami=float(min_tatami) if min_tatami is not None else None,
            target_tatami=float(target_tatami) if target_tatami is not None else None,
        )

    depth_raw = closet_payload.get("depth_mm")
    if depth_raw is None:
        size_raw = closet_payload.get("size_constraints")
        if isinstance(size_raw, dict):
            depth_raw = size_raw.get("min_width")
    depth_mm = int(depth_raw) if depth_raw is not None else None
    if depth_mm is not None and depth_mm % minor != 0:
        raise ValueError(
            f"embedded closet '{closet_payload['id']}' depth_mm must align to minor grid"
        )

    return EmbeddedClosetSpec(
        id=str(closet_payload["id"]),
        parent_id=parent_id,
        area=area,
        depth_mm=depth_mm,
    )


def _space_to_embedded_closet(space: SpaceSpec, floor_id: str) -> EmbeddedClosetSpec:
    """Convert a legacy top-level closet space into embedded closet metadata.

    Args:
        space: Parsed closet ``SpaceSpec``.
        floor_id: Floor identifier for error context.

    Returns:
        Embedded closet metadata preserving area preferences.

    Raises:
        ValueError: If the legacy closet space has no ``parent_id``.
    """
    if space.parent_id is None:
        raise ValueError(f"closet-like space '{space.id}' on {floor_id} requires parent_id")
    return EmbeddedClosetSpec(
        id=space.id,
        parent_id=space.parent_id,
        area=space.area,
        depth_mm=space.size_constraints.min_width,
    )


def _validate_floor_closet_references(
    floor_id: str,
    spaces: list[SpaceSpec],
    embedded_closets: list[EmbeddedClosetSpec],
) -> None:
    """Validate WIC parent references and embedded closet parent references.

    Args:
        floor_id: Floor identifier.
        spaces: Parsed spaces for the floor.
        embedded_closets: Parsed embedded closet metadata for the floor.

    Returns:
        None.

    Raises:
        ValueError: If closet/WIC declarations are missing or invalid.
    """
    ids = {space.id for space in spaces}
    if len(ids) != len(spaces):
        raise ValueError(f"duplicate space id detected on {floor_id}")
    embedded_ids = {closet.id for closet in embedded_closets}
    if len(embedded_ids) != len(embedded_closets):
        raise ValueError(f"duplicate embedded closet id detected on {floor_id}")
    duplicate_between = ids.intersection(embedded_ids)
    if duplicate_between:
        raise ValueError(
            f"embedded closet ids on {floor_id} conflict with space ids: {sorted(duplicate_between)}"
        )
    for space in spaces:
        if space.type not in WALK_IN_CLOSET_SPACE_TYPES:
            continue
        if space.parent_id is None:
            raise ValueError(f"closet-like space '{space.id}' on {floor_id} requires parent_id")
        if space.parent_id == space.id:
            raise ValueError(f"closet-like space '{space.id}' on {floor_id} cannot reference itself as parent")
        if space.parent_id not in ids:
            raise ValueError(
                f"closet-like space '{space.id}' on {floor_id} references unknown parent_id '{space.parent_id}'"
            )
    for closet in embedded_closets:
        if closet.parent_id not in ids:
            raise ValueError(
                f"embedded closet '{closet.id}' on {floor_id} references unknown parent_id '{closet.parent_id}'"
            )
