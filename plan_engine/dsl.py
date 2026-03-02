from __future__ import annotations

from pathlib import Path

import yaml

from plan_engine.constants import (
    CLOSET_SPACE_TYPES,
    MAJOR_GRID_MM,
    MINOR_GRID_MM,
    STAIR_TYPES,
    is_outdoor_space_type,
)
from plan_engine.dsl_closets import (
    _parse_embedded_closets,
    _space_to_embedded_closet,
    _validate_floor_closet_references,
)
from plan_engine.models import (
    AdjacencyRule,
    AreaConstraint,
    BuildableRectSpec,
    CoreSpec,
    EmbeddedClosetSpec,
    EnvelopeSpec,
    FloorSpec,
    GridSpec,
    PlanSpec,
    ShapeSpec,
    SiteSpec,
    SizeConstraints,
    SpaceSpec,
    StairSpec,
    TopologySpec,
)


def load_plan_spec(path: str | Path) -> PlanSpec:
    """Parse a YAML specification file into a PlanSpec.

    Reads the YAML file at *path*, validates that the grid dimensions align to
    the 455 mm minor grid, that units are millimetres, and that the top-level
    schema contains the required ``grid``, ``site``, and ``floors`` sections.

    Args:
        path: Filesystem path to the DSL YAML specification file.

    Returns:
        A fully-populated ``PlanSpec`` instance.

    Raises:
        ValueError: If the file content violates any schema or alignment rule.
    """
    spec_path = Path(path)
    raw = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("plan spec must be a mapping")

    version = str(raw.get("version", "0.2"))
    units = str(raw.get("units", "mm"))
    if units != "mm":
        raise ValueError("only mm units are supported")

    grid_raw = _expect_mapping(raw, "grid")
    minor = int(grid_raw.get("minor", MINOR_GRID_MM))
    major = int(grid_raw.get("major", MAJOR_GRID_MM))
    if minor != MINOR_GRID_MM:
        raise ValueError(f"minor grid must be {MINOR_GRID_MM}")
    if major != MAJOR_GRID_MM:
        raise ValueError(f"major grid should be {MAJOR_GRID_MM} for MVP")

    site_raw = _expect_mapping(raw, "site")
    envelope_raw = _expect_mapping(site_raw, "envelope")
    if envelope_raw.get("type") != "rectangle":
        raise ValueError("only rectangular envelopes are supported in MVP")
    width = int(envelope_raw["width"])
    depth = int(envelope_raw["depth"])
    if width % minor != 0 or depth % minor != 0:
        raise ValueError("site envelope dimensions must align to 455mm grid")
    site = SiteSpec(
        envelope=EnvelopeSpec(type="rectangle", width=width, depth=depth),
        north=str(site_raw.get("north", "top")),
    )

    floors_raw = _expect_mapping(raw, "floors")
    floors: dict[str, FloorSpec] = {}
    for floor_id, floor_payload in floors_raw.items():
        floors[str(floor_id)] = _parse_floor(
            floor_id=str(floor_id),
            payload=_expect_mapping_value(floor_payload),
            minor=minor,
            envelope_width=width,
            envelope_depth=depth,
        )

    return PlanSpec(
        version=version,
        units=units,
        grid=GridSpec(minor=minor, major=major),
        site=site,
        floors=floors,
    )


def _parse_floor(
    floor_id: str,
    payload: dict[str, object],
    minor: int,
    envelope_width: int,
    envelope_depth: int,
) -> FloorSpec:
    """Parse a single floor definition from raw YAML data.

    Extracts the optional core (stair) configuration, the list of spaces, and
    the topology adjacency pairs for the given floor. Also parses an optional
    floor-level buildable mask. Embedded ``closet`` declarations are converted
    to floor-level ``embedded_closets`` metadata, while embedded ``wic``
    declarations remain independent spaces linked by ``parent_id``.

    Args:
        floor_id: Identifier for this floor (e.g. ``"1F"``).
        payload: Dict of raw YAML values for the floor.
        minor: Minor grid size in mm, used for alignment validation.
        envelope_width: Site envelope width in millimeters.
        envelope_depth: Site envelope depth in millimeters.

    Returns:
        A ``FloorSpec`` representing the parsed floor.

    Raises:
        ValueError: If stair dimensions or placements are not grid-aligned,
            or if space / topology entries are malformed.
    """
    core = CoreSpec(stair=None)
    core_raw = payload.get("core")
    if isinstance(core_raw, dict) and isinstance(core_raw.get("stair"), dict):
        stair = _parse_stair_spec(floor_id, _expect_mapping_value(core_raw["stair"]), minor)
        if stair.width % minor != 0:
            raise ValueError("stair width must align to minor grid")
        if stair.placement_x is not None and stair.placement_x % minor != 0:
            raise ValueError("stair placement x must align to minor grid")
        if stair.placement_y is not None and stair.placement_y % minor != 0:
            raise ValueError("stair placement y must align to minor grid")
        core = CoreSpec(stair=stair)

    spaces: list[SpaceSpec] = []
    embedded_closets: list[EmbeddedClosetSpec] = []
    for raw_space in payload.get("spaces", []):
        if not isinstance(raw_space, dict):
            raise ValueError(f"invalid space definition in floor {floor_id}")
        parsed_space = _parse_space(raw_space, minor)
        if parsed_space.type in CLOSET_SPACE_TYPES:
            embedded_closets.append(_space_to_embedded_closet(parsed_space, floor_id=floor_id))
            continue
        spaces.append(parsed_space)
        parsed_embedded, parsed_wics = _parse_embedded_closets(
            raw_parent_space=raw_space,
            parent_space=parsed_space,
            minor=minor,
        )
        embedded_closets.extend(parsed_embedded)
        spaces.extend(parsed_wics)

    _validate_floor_closet_references(
        floor_id=floor_id,
        spaces=spaces,
        embedded_closets=embedded_closets,
    )

    topology_raw = payload.get("topology") or {}
    adjacency_pairs: list[AdjacencyRule] = []
    embedded_closet_ids = {closet.id for closet in embedded_closets}
    if isinstance(topology_raw, dict):
        for pair in topology_raw.get("adjacency", []):
            if not isinstance(pair, list) or len(pair) not in {2, 3}:
                raise ValueError(f"topology adjacency entries must be 2-item or 3-item lists in floor {floor_id}")
            left_id = str(pair[0])
            right_id = str(pair[1])
            if left_id in embedded_closet_ids or right_id in embedded_closet_ids:
                # Embedded closets are interior room features, not topology nodes.
                continue
            strength = "auto"
            if len(pair) == 3:
                strength = str(pair[2]).strip().lower()
                if strength not in {"required", "preferred", "optional"}:
                    raise ValueError(
                        f"unsupported adjacency strength '{pair[2]}' in floor {floor_id}; "
                        "use required/preferred/optional"
                    )
            adjacency_pairs.append(
                AdjacencyRule(
                    left_id=left_id,
                    right_id=right_id,
                    strength=strength,
                )
            )

    buildable_mask = _parse_buildable_mask(
        floor_id=floor_id,
        buildable_raw=payload.get("buildable"),
        minor=minor,
        envelope_width=envelope_width,
        envelope_depth=envelope_depth,
    )

    return FloorSpec(
        id=floor_id,
        core=core,
        spaces=spaces,
        embedded_closets=embedded_closets,
        topology=TopologySpec(adjacency=adjacency_pairs),
        buildable_mask=buildable_mask,
    )


def _parse_space(raw: dict[str, object], minor: int) -> SpaceSpec:
    """Parse a single space definition including area, size, and shape constraints.

    Processes the ``area`` (tatami-based), ``size_constraints`` (min width), and
    ``shape`` (allowed geometries) sub-sections of a space entry. Validates
    grid alignment of size constraints and restricts L2 shapes to eligible
    space types. Optional ``parent_id`` is preserved for WIC and legacy closet
    declarations.

    Args:
        raw: Dict of raw YAML values for one space entry.
        minor: Minor grid size in mm, used for alignment validation.

    Returns:
        A ``SpaceSpec`` representing the parsed space.

    Raises:
        ValueError: If constraints violate grid alignment or shape rules.
    """
    space_id = str(raw["id"])
    space_type = str(raw["type"])
    space_class = "outdoor" if is_outdoor_space_type(space_type) else "indoor"

    area_raw = raw.get("area")
    area = AreaConstraint()
    if isinstance(area_raw, dict):
        min_tatami = area_raw.get("min_tatami")
        target_tatami = area_raw.get("target_tatami")
        area = AreaConstraint(
            min_tatami=float(min_tatami) if min_tatami is not None else None,
            target_tatami=float(target_tatami) if target_tatami is not None else None,
        )

    size_raw = raw.get("size_constraints")
    size = SizeConstraints()
    if isinstance(size_raw, dict):
        min_width = size_raw.get("min_width")
        if min_width is not None:
            min_width = int(min_width)
            if min_width % minor != 0:
                raise ValueError(f"size constraint min_width for '{space_id}' must align to minor grid")
        size = SizeConstraints(min_width=min_width)

    shape_raw = raw.get("shape")
    shape = ShapeSpec()
    if isinstance(shape_raw, dict):
        allow = shape_raw.get("allow", ["rect"])
        if not isinstance(allow, list) or not allow:
            raise ValueError(f"shape.allow for '{space_id}' must be a non-empty list")
        shape = ShapeSpec(
            allow=[str(v) for v in allow],
            rect_components_max=int(shape_raw.get("rect_components_max", 1)),
        )
    if "L2" in shape.allow and space_type not in {"ldk", "hall"}:
        raise ValueError(f"space '{space_id}' of type '{space_type}' cannot use L2 shape in current stage")

    parent_id = raw.get("parent_id")
    if parent_id is not None and not str(parent_id).strip():
        raise ValueError(f"parent_id for '{space_id}' must be a non-empty string when provided")

    return SpaceSpec(
        id=space_id,
        type=space_type,
        space_class=space_class,
        area=area,
        size_constraints=size,
        shape=shape,
        parent_id=str(parent_id) if parent_id is not None else None,
    )


def _parse_stair_spec(floor_id: str, stair_raw: dict[str, object], minor: int) -> StairSpec:
    """Parse a stair specification from raw YAML data.

    Reads stair type, dimensions, riser/tread preferences, connection mapping,
    and optional placement coordinates. Validates that the stair type is one
    of the supported values in ``STAIR_TYPES`` (``straight``, ``L_landing``,
    ``U_turn``).

    Args:
        floor_id: Identifier of the floor this stair belongs to.
        stair_raw: Dict of raw YAML values for the stair entry.
        minor: Minor grid size in mm (used by caller for alignment checks).

    Returns:
        A ``StairSpec`` representing the parsed stair.

    Raises:
        ValueError: If the stair type is unsupported or placement data is
            incomplete.
    """
    stair_type = str(stair_raw["type"])
    if stair_type not in STAIR_TYPES:
        raise ValueError(f"unsupported stair type '{stair_type}' on floor {floor_id}")

    placement_x: int | None = None
    placement_y: int | None = None
    placement_raw = stair_raw.get("placement")
    if placement_raw is not None:
        if not isinstance(placement_raw, dict):
            raise ValueError(f"stair placement must be a mapping on floor {floor_id}")
        if "x" not in placement_raw or "y" not in placement_raw:
            raise ValueError(f"stair placement requires both x and y on floor {floor_id}")
        placement_x = int(placement_raw["x"])
        placement_y = int(placement_raw["y"])

    return StairSpec(
        id=str(stair_raw.get("id", "stair")),
        type=stair_type,
        width=int(stair_raw["width"]),
        floor_height=int(stair_raw["floor_height"]),
        riser_pref=int(stair_raw["riser_pref"]),
        tread_pref=int(stair_raw["tread_pref"]),
        connects={str(k): str(v) for k, v in _expect_mapping(stair_raw, "connects").items()},
        placement_x=placement_x,
        placement_y=placement_y,
    )


def _expect_mapping(root: dict[str, object], key: str) -> dict[str, object]:
    """Extract a dict value for the given key, raising ValueError if not a mapping."""
    value = root.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"'{key}' must be a mapping")
    return value


def _expect_mapping_value(value: object) -> dict[str, object]:
    """Validate that a value is a dict, raising ValueError otherwise."""
    if not isinstance(value, dict):
        raise ValueError("floor definition must be a mapping")
    return value


def _parse_buildable_mask(
    floor_id: str,
    buildable_raw: object,
    minor: int,
    envelope_width: int,
    envelope_depth: int,
) -> list[BuildableRectSpec]:
    """Parse floor buildable mask rectangles.

    Args:
        floor_id: Floor identifier.
        buildable_raw: Raw ``buildable`` YAML value. Supports a list of
            rectangle mappings or ``{\"rects\": [...]}``.
        minor: Minor grid size in millimeters.
        envelope_width: Envelope width used for defaulting.
        envelope_depth: Envelope depth used for defaulting.

    Returns:
        Parsed list of buildable rectangles in millimeters. When omitted,
        defaults to one full-envelope rectangle.

    Raises:
        ValueError: If buildable mask format is invalid or not grid-aligned.
    """
    if buildable_raw is None:
        return [BuildableRectSpec(x=0, y=0, w=envelope_width, h=envelope_depth)]

    rect_items: object
    if isinstance(buildable_raw, list):
        rect_items = buildable_raw
    elif isinstance(buildable_raw, dict):
        if "rects" in buildable_raw:
            rect_items = buildable_raw["rects"]
        elif {"x", "y", "w", "h"}.issubset(buildable_raw.keys()):
            rect_items = [buildable_raw]
        else:
            raise ValueError(f"buildable on floor {floor_id} must be a list or a mapping with 'rects'")
    else:
        raise ValueError(f"buildable on floor {floor_id} must be a list or mapping")

    if not isinstance(rect_items, list) or not rect_items:
        raise ValueError(f"buildable rects on floor {floor_id} must be a non-empty list")

    rects: list[BuildableRectSpec] = []
    for index, rect_raw in enumerate(rect_items):
        if not isinstance(rect_raw, dict):
            raise ValueError(f"buildable rect #{index} on floor {floor_id} must be a mapping")
        missing = {"x", "y", "w", "h"} - set(rect_raw.keys())
        if missing:
            raise ValueError(f"buildable rect #{index} on floor {floor_id} is missing keys: {sorted(missing)}")
        x = int(rect_raw["x"])
        y = int(rect_raw["y"])
        w = int(rect_raw["w"])
        h = int(rect_raw["h"])
        if w <= 0 or h <= 0:
            raise ValueError(f"buildable rect #{index} on floor {floor_id} must have positive size")
        for field_name, value in (("x", x), ("y", y), ("w", w), ("h", h)):
            if value % minor != 0:
                raise ValueError(
                    f"buildable rect #{index} field '{field_name}' on floor {floor_id} must align to {minor}mm grid"
                )
        rects.append(BuildableRectSpec(x=x, y=y, w=w, h=h))
    return rects
