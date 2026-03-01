"""Data models for the plan engine.

Re-exports all public symbols so ``from plan_engine.models import X`` continues
to work after the module-to-package conversion.
"""

from plan_engine.models.geometry import Rect
from plan_engine.models.solution import (
    EmbeddedClosetGeometry,
    FloorSolution,
    PlanSolution,
    SpaceGeometry,
    StairGeometry,
)
from plan_engine.models.spec import (
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
    StairType,
    TopologySpec,
)
from plan_engine.models.structure import (
    ContinuityMetrics,
    FloorStructureMetrics,
    StructureReport,
    VerticalTransferRequirement,
    WallSegment,
)
from plan_engine.models.validation import (
    BedroomReachabilityViolation,
    ValidationReport,
)

__all__ = [
    "AdjacencyRule",
    "AreaConstraint",
    "BedroomReachabilityViolation",
    "BuildableRectSpec",
    "ContinuityMetrics",
    "CoreSpec",
    "EmbeddedClosetGeometry",
    "EmbeddedClosetSpec",
    "EnvelopeSpec",
    "FloorSolution",
    "FloorSpec",
    "FloorStructureMetrics",
    "GridSpec",
    "PlanSolution",
    "PlanSpec",
    "Rect",
    "ShapeSpec",
    "SiteSpec",
    "SizeConstraints",
    "SpaceGeometry",
    "SpaceSpec",
    "StairGeometry",
    "StairSpec",
    "StairType",
    "StructureReport",
    "TopologySpec",
    "ValidationReport",
    "VerticalTransferRequirement",
    "WallSegment",
]
