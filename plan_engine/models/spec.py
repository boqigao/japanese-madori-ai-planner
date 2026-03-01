from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, TypeAlias

StairType: TypeAlias = Literal["straight", "L_landing", "U_turn"]


@dataclass(frozen=True)
class GridSpec:
    """Grid configuration with minor and major grid sizes in mm."""

    minor: int
    major: int

    def to_dict(self) -> dict[str, int]:
        """Return the grid spec as a plain dictionary."""
        return {"minor": self.minor, "major": self.major}


@dataclass(frozen=True)
class EnvelopeSpec:
    """Rectangular site envelope dimensions."""

    type: str
    width: int
    depth: int

    def to_dict(self) -> dict[str, object]:
        """Return the envelope spec as a plain dictionary."""
        return {"type": self.type, "width": self.width, "depth": self.depth}


@dataclass(frozen=True)
class SiteSpec:
    """Site properties including envelope and north orientation."""

    envelope: EnvelopeSpec
    north: str

    def to_dict(self) -> dict[str, object]:
        """Return the site spec as a plain dictionary."""
        return {"envelope": self.envelope.to_dict(), "north": self.north}


@dataclass(frozen=True)
class AreaConstraint:
    """Area bounds in tatami units."""

    min_tatami: float | None = None
    target_tatami: float | None = None


@dataclass(frozen=True)
class SizeConstraints:
    """Dimensional constraints for a space."""

    min_width: int | None = None


@dataclass(frozen=True)
class ShapeSpec:
    """Allowed shapes and component limits for a space."""

    allow: list[str] = field(default_factory=lambda: ["rect"])
    rect_components_max: int = 1


@dataclass(frozen=True)
class BuildableRectSpec:
    """One floor-local buildable-mask rectangle in millimeters."""

    x: int
    y: int
    w: int
    h: int

    def to_dict(self) -> dict[str, int]:
        """Return buildable-mask rectangle as a plain dictionary."""
        return {"x": self.x, "y": self.y, "w": self.w, "h": self.h}


@dataclass(frozen=True)
class SpaceSpec:
    """Complete specification for a single space/room.

    Attributes:
        id: Stable floor-local space identifier.
        type: Canonical space type token (for example ``bedroom`` or ``wic``).
        space_class: Indoor/outdoor class inferred from ``type``.
        area: Area constraints in tatami units.
        size_constraints: Optional dimensional constraints.
        shape: Allowed geometric shape rules.
        parent_id: Optional host-space reference used by closet/WIC semantics.
    """

    id: str
    type: str
    space_class: str = "indoor"
    area: AreaConstraint = field(default_factory=AreaConstraint)
    size_constraints: SizeConstraints = field(default_factory=SizeConstraints)
    shape: ShapeSpec = field(default_factory=ShapeSpec)
    parent_id: str | None = None


@dataclass(frozen=True)
class EmbeddedClosetSpec:
    """Closet metadata embedded inside a parent room.

    Attributes:
        id: Stable closet identifier unique within one floor.
        parent_id: Host room id that owns this closet.
        area: Optional area preferences in tatami units.
        depth_mm: Preferred closet depth in millimeters.
    """

    id: str
    parent_id: str
    area: AreaConstraint = field(default_factory=AreaConstraint)
    depth_mm: int | None = None


@dataclass(frozen=True)
class StairSpec:
    """Stair specification with type, dimensions, and floor connections.

    Attributes:
        id: Stable stair identifier shared across connected floors.
        type: Stair topology token (``straight``, ``L_landing``, ``U_turn``).
        width: Stair body width in millimeters.
        floor_height: Floor-to-floor height in millimeters.
        riser_pref: Preferred riser size in millimeters.
        tread_pref: Preferred tread size in millimeters.
        connects: Mapping ``{floor_id: hall_id}`` for portal connectivity.
        placement_x: Optional fixed stair anchor X coordinate in millimeters.
        placement_y: Optional fixed stair anchor Y coordinate in millimeters.
    """

    id: str
    type: StairType
    width: int
    floor_height: int
    riser_pref: int
    tread_pref: int
    connects: dict[str, str]
    placement_x: int | None = None
    placement_y: int | None = None


@dataclass(frozen=True)
class CoreSpec:
    """Core structural elements (stair)."""

    stair: StairSpec | None = None


@dataclass(frozen=True)
class AdjacencyRule:
    """Adjacency rule between two entities.

    Attributes:
        left_id: Left entity ID in the relation.
        right_id: Right entity ID in the relation.
        strength: Constraint strength, one of ``required``, ``preferred``,
            ``optional``, or ``auto``.
    """

    left_id: str
    right_id: str
    strength: str = "required"

    def to_tuple(self) -> tuple[str, str]:
        """Return the adjacency as a simple ID pair."""
        return self.left_id, self.right_id


@dataclass(frozen=True)
class TopologySpec:
    """Adjacency relationships between spaces."""

    adjacency: list[AdjacencyRule] = field(default_factory=list)


@dataclass(frozen=True)
class FloorSpec:
    """Complete specification for a single floor."""

    id: str
    core: CoreSpec = field(default_factory=CoreSpec)
    spaces: list[SpaceSpec] = field(default_factory=list)
    embedded_closets: list[EmbeddedClosetSpec] = field(default_factory=list)
    topology: TopologySpec = field(default_factory=TopologySpec)
    buildable_mask: list[BuildableRectSpec] = field(default_factory=list)


@dataclass(frozen=True)
class PlanSpec:
    """Top-level specification for an entire plan."""

    version: str
    units: str
    grid: GridSpec
    site: SiteSpec
    floors: dict[str, FloorSpec]
