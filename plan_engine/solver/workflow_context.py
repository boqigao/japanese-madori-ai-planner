from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ortools.sat.python import cp_model

from plan_engine.constants import mm_to_cells
from plan_engine.solver.rect_var import (
    RectVar,
    StairFootprint,
    _compute_stair_footprint,
    _find_global_stair,
    _slug,
)
from plan_engine.stair_logic import ordered_floor_ids

if TYPE_CHECKING:
    from plan_engine.models import PlanSpec, StairSpec


@dataclass
class SolveContext:
    """Mutable container holding all state for a single solve run."""

    model: cp_model.CpModel
    envelope_w_cells: int
    envelope_h_cells: int
    max_area: int
    placements: dict[str, dict[str, list[RectVar]]]
    target_shortfalls: list[tuple[cp_model.IntVar, int]]
    target_overshoots: list[tuple[cp_model.IntVar, int]]
    major_room_alignment_penalties: list[cp_model.IntVar]
    shape_balance_penalties: list[cp_model.IntVar]
    hall_area_penalties: list[cp_model.IntVar]
    floor_compactness_terms: list[cp_model.IntVar]
    topology_soft_penalties: list[tuple[cp_model.IntVar, int]]
    orientation_soft_penalties: list[tuple[cp_model.IntVar, int]]
    floor_area_vars: dict[str, list[cp_model.IntVar]]
    floor_indoor_area_vars: dict[str, list[cp_model.IntVar]]
    floor_buildable_masks: dict[str, list[tuple[int, int, int, int]]]
    floor_buildable_area_cells: dict[str, int]
    ordered_floors: list[str]
    floor_rank: dict[str, int]
    stair_spec: StairSpec | None
    stair_footprint: StairFootprint | None
    stair_x: cp_model.IntVar | None
    stair_y: cp_model.IntVar | None
    floors_with_stair: set[str]
    skip_portal_edge: bool
    skip_internal_portal: bool
    debug_solver: bool
    forced_stair_x_cells: int | None
    forced_stair_y_cells: int | None


def build_context(spec: PlanSpec) -> SolveContext:
    """Initialize a SolveContext from a PlanSpec, including stair setup and environment parsing."""
    skip_portal_edge = os.getenv("PLAN_ENGINE_SKIP_PORTAL_EDGE") == "1"
    skip_internal_portal = os.getenv("PLAN_ENGINE_SKIP_INTERNAL_PORTAL") == "1"
    debug_solver = os.getenv("PLAN_ENGINE_DEBUG_SOLVER") == "1"
    forced_stair_x_cells_raw = os.getenv("PLAN_ENGINE_FORCE_STAIR_X_CELLS")
    forced_stair_y_cells_raw = os.getenv("PLAN_ENGINE_FORCE_STAIR_Y_CELLS")
    forced_stair_x_cells = int(forced_stair_x_cells_raw) if forced_stair_x_cells_raw is not None else None
    forced_stair_y_cells = int(forced_stair_y_cells_raw) if forced_stair_y_cells_raw is not None else None

    envelope_w_cells = mm_to_cells(spec.site.envelope.width, spec.grid.minor)
    envelope_h_cells = mm_to_cells(spec.site.envelope.depth, spec.grid.minor)
    max_area = envelope_w_cells * envelope_h_cells
    model = cp_model.CpModel()

    placements: dict[str, dict[str, list[RectVar]]] = {fid: {} for fid in spec.floors}
    target_shortfalls: list[tuple[cp_model.IntVar, int]] = []
    target_overshoots: list[tuple[cp_model.IntVar, int]] = []
    major_room_alignment_penalties: list[cp_model.IntVar] = []
    shape_balance_penalties: list[cp_model.IntVar] = []
    hall_area_penalties: list[cp_model.IntVar] = []
    floor_compactness_terms: list[cp_model.IntVar] = []
    topology_soft_penalties: list[tuple[cp_model.IntVar, int]] = []
    orientation_soft_penalties: list[tuple[cp_model.IntVar, int]] = []
    floor_area_vars: dict[str, list[cp_model.IntVar]] = {fid: [] for fid in spec.floors}
    floor_indoor_area_vars: dict[str, list[cp_model.IntVar]] = {fid: [] for fid in spec.floors}
    floor_buildable_masks: dict[str, list[tuple[int, int, int, int]]] = {}
    floor_buildable_area_cells: dict[str, int] = {}

    for floor_id, floor in spec.floors.items():
        mask_cells: list[tuple[int, int, int, int]] = []
        if floor.buildable_mask:
            for rect in floor.buildable_mask:
                mask_cells.append(
                    (
                        mm_to_cells(rect.x, spec.grid.minor),
                        mm_to_cells(rect.y, spec.grid.minor),
                        mm_to_cells(rect.w, spec.grid.minor),
                        mm_to_cells(rect.h, spec.grid.minor),
                    )
                )
        if not mask_cells:
            mask_cells = [(0, 0, envelope_w_cells, envelope_h_cells)]
        floor_buildable_masks[floor_id] = mask_cells
        floor_buildable_area_cells[floor_id] = sum(w * h for _, _, w, h in mask_cells)

    ordered_floors = ordered_floor_ids(spec.floors.keys())
    floor_rank = {floor_id: idx for idx, floor_id in enumerate(ordered_floors)}
    stair_spec = _find_global_stair(spec)
    stair_footprint: StairFootprint | None = None
    stair_x: cp_model.IntVar | None = None
    stair_y: cp_model.IntVar | None = None
    floors_with_stair: set[str] = set()

    if stair_spec is not None:
        stair_footprint, stair_x, stair_y = _create_stair_anchor(
            model=model,
            spec=spec,
            stair_spec=stair_spec,
            envelope_w_cells=envelope_w_cells,
            envelope_h_cells=envelope_h_cells,
            forced_stair_x_cells=forced_stair_x_cells,
            forced_stair_y_cells=forced_stair_y_cells,
        )
        floors_with_stair = set(stair_spec.connects.keys())
        floors_with_stair.update(floor_id for floor_id, floor in spec.floors.items() if floor.core.stair is not None)
        floors_with_stair.intersection_update(spec.floors.keys())

    return SolveContext(
        model=model,
        envelope_w_cells=envelope_w_cells,
        envelope_h_cells=envelope_h_cells,
        max_area=max_area,
        placements=placements,
        target_shortfalls=target_shortfalls,
        target_overshoots=target_overshoots,
        major_room_alignment_penalties=major_room_alignment_penalties,
        shape_balance_penalties=shape_balance_penalties,
        hall_area_penalties=hall_area_penalties,
        floor_compactness_terms=floor_compactness_terms,
        topology_soft_penalties=topology_soft_penalties,
        orientation_soft_penalties=orientation_soft_penalties,
        floor_area_vars=floor_area_vars,
        floor_indoor_area_vars=floor_indoor_area_vars,
        floor_buildable_masks=floor_buildable_masks,
        floor_buildable_area_cells=floor_buildable_area_cells,
        ordered_floors=ordered_floors,
        floor_rank=floor_rank,
        stair_spec=stair_spec,
        stair_footprint=stair_footprint,
        stair_x=stair_x,
        stair_y=stair_y,
        floors_with_stair=floors_with_stair,
        skip_portal_edge=skip_portal_edge,
        skip_internal_portal=skip_internal_portal,
        debug_solver=debug_solver,
        forced_stair_x_cells=forced_stair_x_cells,
        forced_stair_y_cells=forced_stair_y_cells,
    )


def _create_stair_anchor(
    model: cp_model.CpModel,
    spec: PlanSpec,
    stair_spec: StairSpec,
    envelope_w_cells: int,
    envelope_h_cells: int,
    forced_stair_x_cells: int | None,
    forced_stair_y_cells: int | None,
) -> tuple[StairFootprint, cp_model.IntVar, cp_model.IntVar]:
    """Create shared stair position variables and compute stair footprint."""
    stair_footprint = _compute_stair_footprint(stair_spec, spec.grid.minor)
    stair_x = model.NewIntVar(
        0,
        envelope_w_cells - stair_footprint.w_cells,
        f"{_slug(stair_spec.id)}_x",
    )
    stair_y = model.NewIntVar(
        0,
        envelope_h_cells - stair_footprint.h_cells,
        f"{_slug(stair_spec.id)}_y",
    )

    stair_x_cells = forced_stair_x_cells
    stair_y_cells = forced_stair_y_cells
    if stair_x_cells is None and stair_spec.placement_x is not None:
        stair_x_cells = mm_to_cells(stair_spec.placement_x, spec.grid.minor)
    if stair_y_cells is None and stair_spec.placement_y is not None:
        stair_y_cells = mm_to_cells(stair_spec.placement_y, spec.grid.minor)

    if stair_x_cells is not None:
        if stair_x_cells < 0 or stair_x_cells > envelope_w_cells - stair_footprint.w_cells:
            raise ValueError("PLAN_ENGINE_FORCE_STAIR_X_CELLS is out of range")
        model.Add(stair_x == stair_x_cells)
    if stair_y_cells is not None:
        if stair_y_cells < 0 or stair_y_cells > envelope_h_cells - stair_footprint.h_cells:
            raise ValueError("PLAN_ENGINE_FORCE_STAIR_Y_CELLS is out of range")
        model.Add(stair_y == stair_y_cells)

    return stair_footprint, stair_x, stair_y


def _constrain_rect_within_buildable_union(
    model: cp_model.CpModel,
    rect: RectVar,
    allowed_regions: list[tuple[int, int, int, int]],
    prefix: str,
) -> None:
    """Constrain one rectangle to lie fully inside a union of allowed regions.

    Args:
        model: CP-SAT model receiving constraints.
        rect: Rectangle variable to constrain.
        allowed_regions: Regions as ``(x, y, w, h)`` in cell units.
        prefix: Variable-name prefix for helper booleans.

    Returns:
        None. Constraints are added in-place.
    """
    if len(allowed_regions) == 1:
        x, y, w, h = allowed_regions[0]
        model.Add(rect.x >= x)
        model.Add(rect.y >= y)
        model.Add(rect.x_end <= x + w)
        model.Add(rect.y_end <= y + h)
        return

    indicators: list[cp_model.IntVar] = []
    for index, (x, y, w, h) in enumerate(allowed_regions):
        inside = model.NewBoolVar(f"{prefix}_in_buildable_{index}")
        indicators.append(inside)
        model.Add(rect.x >= x).OnlyEnforceIf(inside)
        model.Add(rect.y >= y).OnlyEnforceIf(inside)
        model.Add(rect.x_end <= x + w).OnlyEnforceIf(inside)
        model.Add(rect.y_end <= y + h).OnlyEnforceIf(inside)
    model.AddBoolOr(indicators)
