from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GridSpec:
    minor: int
    major: int

    def to_dict(self) -> dict[str, int]:
        return {"minor": self.minor, "major": self.major}


@dataclass(frozen=True)
class EnvelopeSpec:
    type: str
    width: int
    depth: int

    def to_dict(self) -> dict[str, object]:
        return {"type": self.type, "width": self.width, "depth": self.depth}


@dataclass(frozen=True)
class SiteSpec:
    envelope: EnvelopeSpec
    north: str

    def to_dict(self) -> dict[str, object]:
        return {"envelope": self.envelope.to_dict(), "north": self.north}


@dataclass(frozen=True)
class AreaConstraint:
    min_tatami: float | None = None
    target_tatami: float | None = None


@dataclass(frozen=True)
class SizeConstraints:
    min_width: int | None = None


@dataclass(frozen=True)
class ShapeSpec:
    allow: list[str] = field(default_factory=lambda: ["rect"])
    rect_components_max: int = 1


@dataclass(frozen=True)
class SpaceSpec:
    id: str
    type: str
    area: AreaConstraint = field(default_factory=AreaConstraint)
    size_constraints: SizeConstraints = field(default_factory=SizeConstraints)
    shape: ShapeSpec = field(default_factory=ShapeSpec)


@dataclass(frozen=True)
class StairSpec:
    id: str
    type: str
    width: int
    floor_height: int
    riser_pref: int
    tread_pref: int
    connects: dict[str, str]
    placement_x: int | None = None
    placement_y: int | None = None


@dataclass(frozen=True)
class CoreSpec:
    stair: StairSpec | None = None


@dataclass(frozen=True)
class TopologySpec:
    adjacency: list[tuple[str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class FloorSpec:
    id: str
    core: CoreSpec = field(default_factory=CoreSpec)
    spaces: list[SpaceSpec] = field(default_factory=list)
    topology: TopologySpec = field(default_factory=TopologySpec)


@dataclass(frozen=True)
class PlanSpec:
    version: str
    units: str
    grid: GridSpec
    site: SiteSpec
    floors: dict[str, FloorSpec]


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    w: int
    h: int

    @property
    def x2(self) -> int:
        return self.x + self.w

    @property
    def y2(self) -> int:
        return self.y + self.h

    @property
    def area(self) -> int:
        return self.w * self.h

    def to_dict(self) -> dict[str, int]:
        return {"x": self.x, "y": self.y, "w": self.w, "h": self.h}

    def overlaps(self, other: "Rect") -> bool:
        return not (
            self.x2 <= other.x
            or other.x2 <= self.x
            or self.y2 <= other.y
            or other.y2 <= self.y
        )

    def shares_edge_with(self, other: "Rect") -> bool:
        if self.x2 == other.x or other.x2 == self.x:
            y_overlap = min(self.y2, other.y2) - max(self.y, other.y)
            return y_overlap > 0
        if self.y2 == other.y or other.y2 == self.y:
            x_overlap = min(self.x2, other.x2) - max(self.x, other.x)
            return x_overlap > 0
        return False

    def shared_edge_segment(
        self, other: "Rect"
    ) -> tuple[tuple[int, int], tuple[int, int]] | None:
        if self.x2 == other.x or other.x2 == self.x:
            y1 = max(self.y, other.y)
            y2 = min(self.y2, other.y2)
            if y2 > y1:
                edge_x = other.x if self.x2 == other.x else self.x
                return (edge_x, y1), (edge_x, y2)
        if self.y2 == other.y or other.y2 == self.y:
            x1 = max(self.x, other.x)
            x2 = min(self.x2, other.x2)
            if x2 > x1:
                edge_y = other.y if self.y2 == other.y else self.y
                return (x1, edge_y), (x2, edge_y)
        return None


@dataclass(frozen=True)
class SpaceGeometry:
    id: str
    type: str
    rects: list[Rect]

    def to_dict(self) -> dict[str, object]:
        return {"id": self.id, "type": self.type, "rects": [r.to_dict() for r in self.rects]}


@dataclass(frozen=True)
class StairGeometry:
    id: str
    type: str
    bbox: Rect
    components: list[Rect]
    floor_height: int
    riser_count: int
    tread_count: int
    riser_mm: int
    tread_mm: int
    landing_size: tuple[int, int]
    connects: dict[str, str]
    portal_component: int | None = None
    portal_edge: str | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "id": self.id,
            "type": self.type,
            "bbox": self.bbox.to_dict(),
            "components": [component.to_dict() for component in self.components],
            "floor_height": self.floor_height,
            "riser_count": self.riser_count,
            "tread_count": self.tread_count,
            "riser_mm": self.riser_mm,
            "tread_mm": self.tread_mm,
            "landing_size": {"w": self.landing_size[0], "h": self.landing_size[1]},
            "connects": dict(self.connects),
        }
        if self.portal_component is not None and self.portal_edge is not None:
            payload["portal"] = {
                "component_index": self.portal_component,
                "edge": self.portal_edge,
            }
        return payload


@dataclass(frozen=True)
class FloorSolution:
    id: str
    spaces: dict[str, SpaceGeometry]
    stair: StairGeometry | None
    topology: list[tuple[str, str]]

    def to_dict(self) -> dict[str, object]:
        ordered_spaces = [self.spaces[sid].to_dict() for sid in sorted(self.spaces)]
        payload: dict[str, object] = {
            "spaces": ordered_spaces,
            "topology": [[a, b] for a, b in self.topology],
        }
        if self.stair is not None:
            payload["stair"] = self.stair.to_dict()
        return payload


@dataclass(frozen=True)
class PlanSolution:
    units: str
    grid: GridSpec
    envelope: EnvelopeSpec
    north: str
    floors: dict[str, FloorSolution]

    def to_dict(self) -> dict[str, object]:
        return {
            "units": self.units,
            "grid": self.grid.to_dict(),
            "site": {"envelope": self.envelope.to_dict(), "north": self.north},
            "floors": {fid: floor.to_dict() for fid, floor in self.floors.items()},
        }


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def to_text(self) -> str:
        lines = [f"valid={self.is_valid}", f"errors={len(self.errors)}", f"warnings={len(self.warnings)}"]
        if self.errors:
            lines.append("")
            lines.append("Errors:")
            for item in self.errors:
                lines.append(f"- {item}")
        if self.warnings:
            lines.append("")
            lines.append("Warnings:")
            for item in self.warnings:
                lines.append(f"- {item}")
        return "\n".join(lines) + "\n"
