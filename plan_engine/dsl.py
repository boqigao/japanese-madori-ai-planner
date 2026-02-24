from __future__ import annotations

from pathlib import Path

import yaml

from .constants import MAJOR_GRID_MM, MINOR_GRID_MM
from .models import (
    AreaConstraint,
    CoreSpec,
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
        floors[str(floor_id)] = _parse_floor(str(floor_id), _expect_mapping_value(floor_payload), minor)

    return PlanSpec(
        version=version,
        units=units,
        grid=GridSpec(minor=minor, major=major),
        site=site,
        floors=floors,
    )


def _parse_floor(floor_id: str, payload: dict[str, object], minor: int) -> FloorSpec:
    core = CoreSpec(stair=None)
    core_raw = payload.get("core")
    if isinstance(core_raw, dict) and isinstance(core_raw.get("stair"), dict):
        stair_raw = core_raw["stair"]
        stair_type = str(stair_raw["type"])
        if stair_type not in {"straight", "L_landing"}:
            raise ValueError(f"unsupported stair type '{stair_type}' on floor {floor_id}")
        stair = StairSpec(
            id=str(stair_raw.get("id", "stair")),
            type=stair_type,
            width=int(stair_raw["width"]),
            floor_height=int(stair_raw["floor_height"]),
            riser_pref=int(stair_raw["riser_pref"]),
            tread_pref=int(stair_raw["tread_pref"]),
            connects={str(k): str(v) for k, v in _expect_mapping(stair_raw, "connects").items()},
        )
        if stair.width % minor != 0:
            raise ValueError("stair width must align to minor grid")
        core = CoreSpec(stair=stair)

    spaces: list[SpaceSpec] = []
    for raw_space in payload.get("spaces", []):
        if not isinstance(raw_space, dict):
            raise ValueError(f"invalid space definition in floor {floor_id}")
        spaces.append(_parse_space(raw_space, minor))

    topology_raw = payload.get("topology") or {}
    adjacency_pairs: list[tuple[str, str]] = []
    if isinstance(topology_raw, dict):
        for pair in topology_raw.get("adjacency", []):
            if not isinstance(pair, list) or len(pair) != 2:
                raise ValueError(f"topology adjacency entries must be 2-item lists in floor {floor_id}")
            adjacency_pairs.append((str(pair[0]), str(pair[1])))

    return FloorSpec(id=floor_id, core=core, spaces=spaces, topology=TopologySpec(adjacency=adjacency_pairs))


def _parse_space(raw: dict[str, object], minor: int) -> SpaceSpec:
    space_id = str(raw["id"])
    space_type = str(raw["type"])

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

    return SpaceSpec(
        id=space_id,
        type=space_type,
        area=area,
        size_constraints=size,
        shape=shape,
    )


def _expect_mapping(root: dict[str, object], key: str) -> dict[str, object]:
    value = root.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"'{key}' must be a mapping")
    return value


def _expect_mapping_value(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError("floor definition must be a mapping")
    return value
