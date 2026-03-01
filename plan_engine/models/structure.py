from __future__ import annotations

from dataclasses import dataclass, field


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
