from __future__ import annotations

from dataclasses import dataclass, field


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
    """Complete specification for a single space/room."""

    id: str
    type: str
    space_class: str = "indoor"
    area: AreaConstraint = field(default_factory=AreaConstraint)
    size_constraints: SizeConstraints = field(default_factory=SizeConstraints)
    shape: ShapeSpec = field(default_factory=ShapeSpec)


@dataclass(frozen=True)
class StairSpec:
    """Stair specification with type, dimensions, and floor connections."""

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


@dataclass(frozen=True)
class Rect:
    """Immutable rectangle with geometry query methods."""

    x: int
    y: int
    w: int
    h: int

    @property
    def x2(self) -> int:
        """Right edge x-coordinate (x + w)."""
        return self.x + self.w

    @property
    def y2(self) -> int:
        """Bottom edge y-coordinate (y + h)."""
        return self.y + self.h

    @property
    def area(self) -> int:
        """Area of the rectangle in square units."""
        return self.w * self.h

    def to_dict(self) -> dict[str, int]:
        """Return the rectangle as a plain dictionary."""
        return {"x": self.x, "y": self.y, "w": self.w, "h": self.h}

    def overlaps(self, other: Rect) -> bool:
        """Return True if this rectangle overlaps with *other*."""
        return not (self.x2 <= other.x or other.x2 <= self.x or self.y2 <= other.y or other.y2 <= self.y)

    def shares_edge_with(self, other: Rect) -> bool:
        """Return True if this rectangle shares a non-zero-length edge with *other*."""
        if self.x2 == other.x or other.x2 == self.x:
            y_overlap = min(self.y2, other.y2) - max(self.y, other.y)
            return y_overlap > 0
        if self.y2 == other.y or other.y2 == self.y:
            x_overlap = min(self.x2, other.x2) - max(self.x, other.x)
            return x_overlap > 0
        return False

    def shared_edge_segment(self, other: Rect) -> tuple[tuple[int, int], tuple[int, int]] | None:
        """Return the shared edge as a pair of endpoints, or None if no edge is shared."""
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
    """Solved geometry for a space."""

    id: str
    type: str
    rects: list[Rect]
    space_class: str = "indoor"

    def to_dict(self) -> dict[str, object]:
        """Return the space geometry as a plain dictionary."""
        return {
            "id": self.id,
            "type": self.type,
            "class": self.space_class,
            "rects": [r.to_dict() for r in self.rects],
        }


@dataclass(frozen=True)
class StairGeometry:
    """Solved geometry for a stair including portal information."""

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
        """Return the stair geometry as a plain dictionary."""
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
class WallSegment:
    """One extracted wall segment on a grid-aligned line."""

    id: str
    floor_id: str
    orientation: str
    line_coord_mm: int
    span_start_mm: int
    span_end_mm: int
    role: str
    kind: str

    @property
    def length_mm(self) -> int:
        """Return segment length in millimeters."""
        return self.span_end_mm - self.span_start_mm

    def to_dict(self) -> dict[str, object]:
        """Return this wall segment as a plain dictionary."""
        return {
            "id": self.id,
            "floor_id": self.floor_id,
            "orientation": self.orientation,
            "line_coord_mm": self.line_coord_mm,
            "span_mm": [self.span_start_mm, self.span_end_mm],
            "length_mm": self.length_mm,
            "role": self.role,
            "kind": self.kind,
        }


@dataclass(frozen=True)
class FloorStructureMetrics:
    """Structural wall-length metrics aggregated for one floor."""

    floor_id: str
    total_wall_length_mm: int
    total_bearing_length_mm: int
    bearing_vertical_mm: int
    bearing_horizontal_mm: int
    quadrant_bearing_mm: tuple[int, int, int, int]
    wall_balance_ratio: float | None

    def to_dict(self) -> dict[str, object]:
        """Return floor structural metrics as a plain dictionary."""
        return {
            "floor_id": self.floor_id,
            "total_wall_length_mm": self.total_wall_length_mm,
            "total_bearing_length_mm": self.total_bearing_length_mm,
            "bearing_vertical_mm": self.bearing_vertical_mm,
            "bearing_horizontal_mm": self.bearing_horizontal_mm,
            "quadrant_bearing_mm": list(self.quadrant_bearing_mm),
            "wall_balance_ratio": self.wall_balance_ratio,
        }


@dataclass(frozen=True)
class ContinuityMetrics:
    """Cross-floor direct-below continuity metrics for one axis."""

    lower_floor_id: str
    upper_floor_id: str
    orientation: str
    upper_bearing_length_mm: int
    supported_length_mm: int
    direct_below_ratio: float | None

    def to_dict(self) -> dict[str, object]:
        """Return continuity metrics as a plain dictionary."""
        return {
            "lower_floor_id": self.lower_floor_id,
            "upper_floor_id": self.upper_floor_id,
            "orientation": self.orientation,
            "upper_bearing_length_mm": self.upper_bearing_length_mm,
            "supported_length_mm": self.supported_length_mm,
            "direct_below_ratio": self.direct_below_ratio,
        }


@dataclass(frozen=True)
class VerticalTransferRequirement:
    """Unsupported upper-floor bearing span requiring transfer elements."""

    upper_floor_id: str
    segment_id: str
    orientation: str
    line_coord_mm: int
    span_start_mm: int
    span_end_mm: int
    unsupported_length_mm: int

    def to_dict(self) -> dict[str, object]:
        """Return transfer requirement as a plain dictionary."""
        return {
            "upper_floor_id": self.upper_floor_id,
            "segment_id": self.segment_id,
            "orientation": self.orientation,
            "line_coord_mm": self.line_coord_mm,
            "span_mm": [self.span_start_mm, self.span_end_mm],
            "unsupported_length_mm": self.unsupported_length_mm,
        }


@dataclass(frozen=True)
class StructureReport:
    """Computed structural diagnostics and continuity findings."""

    floor_metrics: dict[str, FloorStructureMetrics]
    continuity_metrics: list[ContinuityMetrics]
    vertical_transfer_required: list[VerticalTransferRequirement]
    warnings: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """Return structure diagnostics as a plain dictionary."""
        return {
            "floor_metrics": {floor_id: metrics.to_dict() for floor_id, metrics in self.floor_metrics.items()},
            "continuity_metrics": [item.to_dict() for item in self.continuity_metrics],
            "vertical_transfer_required": [item.to_dict() for item in self.vertical_transfer_required],
            "warnings": list(self.warnings),
            "assumptions": list(self.assumptions),
        }


@dataclass(frozen=True)
class FloorSolution:
    """Solved layout for a single floor."""

    id: str
    spaces: dict[str, SpaceGeometry]
    stair: StairGeometry | None
    topology: list[tuple[str, str]]
    buildable_mask: list[Rect] = field(default_factory=list)
    indoor_buildable_area_mm2: int | None = None

    def to_dict(self) -> dict[str, object]:
        """Return the floor solution as a plain dictionary."""
        ordered_spaces = [self.spaces[sid].to_dict() for sid in sorted(self.spaces)]
        payload: dict[str, object] = {
            "spaces": ordered_spaces,
            "topology": [[a, b] for a, b in self.topology],
        }
        if self.stair is not None:
            payload["stair"] = self.stair.to_dict()
        if self.buildable_mask:
            payload["buildable_mask"] = [rect.to_dict() for rect in self.buildable_mask]
        if self.indoor_buildable_area_mm2 is not None:
            payload["indoor_buildable_area_mm2"] = self.indoor_buildable_area_mm2
        return payload


@dataclass(frozen=True)
class PlanSolution:
    """Complete solved plan with all floors."""

    units: str
    grid: GridSpec
    envelope: EnvelopeSpec
    north: str
    floors: dict[str, FloorSolution]
    walls: dict[str, list[WallSegment]] = field(default_factory=dict)
    structure_report: StructureReport | None = None

    def to_dict(self) -> dict[str, object]:
        """Return the full plan solution as a plain dictionary."""
        payload: dict[str, object] = {
            "units": self.units,
            "grid": self.grid.to_dict(),
            "site": {"envelope": self.envelope.to_dict(), "north": self.north},
            "floors": {fid: floor.to_dict() for fid, floor in self.floors.items()},
        }
        if self.walls:
            payload["walls"] = {floor_id: [wall.to_dict() for wall in walls] for floor_id, walls in self.walls.items()}
        if self.structure_report is not None:
            payload["structure_report"] = self.structure_report.to_dict()
        return payload


@dataclass
class ValidationReport:
    """Mutable report collecting errors and warnings."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    structural: list[str] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Return True if the report contains no errors."""
        return len(self.errors) == 0

    def to_text(self) -> str:
        """Format the report as human-readable plain text.

        Returns:
            A stable, sectioned text representation used by ``report.txt``.
            Sections appear only when they contain at least one item.
        """
        lines = [
            f"valid={self.is_valid}",
            f"errors={len(self.errors)}",
            f"warnings={len(self.warnings)}",
            f"structural={len(self.structural)}",
        ]
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
        if self.structural:
            lines.append("")
            lines.append("Structural:")
            for item in self.structural:
                lines.append(f"- {item}")
        if self.diagnostics:
            lines.append("")
            lines.append("Diagnostics:")
            for item in self.diagnostics:
                lines.append(f"- {item}")
        if self.suggestions:
            lines.append("")
            lines.append("Suggestions:")
            for item in self.suggestions:
                lines.append(f"- {item}")
        return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class BedroomReachabilityViolation:
    """Structured preflight finding for bedroom pass-through circulation.

    Attributes:
        floor_id: Floor identifier containing the blocked bedroom.
        bedroom_id: Target bedroom-like space ID that is blocked.
        transit_bedroom_ids: Ordered tuple of bedroom-like IDs that appear as
            intermediate nodes on a discovered entry-to-target path.
        path: Ordered tuple of floor-local node IDs from entry to target used
            as representative path evidence.
    """

    floor_id: str
    bedroom_id: str
    transit_bedroom_ids: tuple[str, ...]
    path: tuple[str, ...]
