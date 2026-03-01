from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from plan_engine.models.geometry import Rect
    from plan_engine.models.spec import EnvelopeSpec, GridSpec, StairType
    from plan_engine.models.structure import StructureReport, WallSegment


@dataclass(frozen=True)
class SpaceGeometry:
    """Solved geometry for a space.

    Attributes:
        id: Stable space identifier.
        type: Canonical space type token.
        rects: Solved rectangle components in millimeters.
        space_class: Indoor/outdoor class.
        parent_id: Optional host-space reference for closet/WIC semantics.
    """

    id: str
    type: str
    rects: list[Rect]
    space_class: str = "indoor"
    parent_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Return the space geometry as a plain dictionary."""
        payload: dict[str, object] = {
            "id": self.id,
            "type": self.type,
            "class": self.space_class,
            "rects": [r.to_dict() for r in self.rects],
        }
        if self.parent_id is not None:
            payload["parent_id"] = self.parent_id
        return payload


@dataclass(frozen=True)
class EmbeddedClosetGeometry:
    """Solved geometry for one embedded closet strip inside a parent room.

    Attributes:
        id: Closet identifier.
        parent_id: Host room identifier.
        rect: Embedded closet rectangle in millimeters.
    """

    id: str
    parent_id: str
    rect: Rect

    def to_dict(self) -> dict[str, object]:
        """Return embedded closet geometry as a plain dictionary."""
        return {
            "id": self.id,
            "parent_id": self.parent_id,
            "rect": self.rect.to_dict(),
        }


@dataclass(frozen=True)
class StairGeometry:
    """Solved geometry for a stair including component and portal metadata.

    Attributes:
        id: Stair identifier.
        type: Solved stair topology token.
        bbox: Bounding box of all stair components.
        components: Stair component rectangles in deterministic index order.
        floor_height: Floor-to-floor height in millimeters.
        riser_count: Number of risers.
        tread_count: Number of treads.
        riser_mm: Effective riser size in millimeters.
        tread_mm: Effective tread size in millimeters.
        landing_size: Landing size ``(w, h)`` in millimeters.
        connects: Mapping ``{floor_id: hall_id}`` from DSL.
        portal_component: Connected component index for this floor.
        portal_edge: Connected component edge token.
    """

    id: str
    type: StairType
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
class FloorSolution:
    """Solved layout for a single floor."""

    id: str
    spaces: dict[str, SpaceGeometry]
    stair: StairGeometry | None
    topology: list[tuple[str, str]]
    embedded_closets: list[EmbeddedClosetGeometry] = field(default_factory=list)
    buildable_mask: list[Rect] = field(default_factory=list)
    indoor_buildable_area_mm2: int | None = None

    def to_dict(self) -> dict[str, object]:
        """Return the floor solution as a plain dictionary."""
        ordered_spaces = [self.spaces[sid].to_dict() for sid in sorted(self.spaces)]
        payload: dict[str, object] = {
            "spaces": ordered_spaces,
            "topology": [[a, b] for a, b in self.topology],
        }
        if self.embedded_closets:
            payload["embedded_closets"] = [closet.to_dict() for closet in self.embedded_closets]
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
