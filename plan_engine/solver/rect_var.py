from __future__ import annotations

import math
from dataclasses import dataclass

from ortools.sat.python import cp_model

from plan_engine.constants import ceil_to_grid, mm_to_cells
from plan_engine.models import PlanSpec, StairSpec


@dataclass
class RectVar:
    """CP-SAT decision variables representing a rectangle's position, size, and intervals."""

    x: cp_model.IntVar
    y: cp_model.IntVar
    w: cp_model.IntVar
    h: cp_model.IntVar
    x_end: cp_model.IntVar
    y_end: cp_model.IntVar
    area: cp_model.IntVar
    x_interval: cp_model.IntervalVar
    y_interval: cp_model.IntervalVar


@dataclass(frozen=True)
class StairFootprint:
    """Computed stair geometry in grid cell units."""

    w_cells: int
    h_cells: int
    components: list[tuple[str, int, int, int, int]]
    riser_count: int
    tread_count: int
    riser_mm: int
    tread_mm: int
    landing_mm: tuple[int, int]


def _find_global_stair(spec: PlanSpec) -> StairSpec | None:
    """Find the shared stair specification across all floors. Raises if multiple distinct stair IDs found."""
    stair: StairSpec | None = None
    for floor in spec.floors.values():
        if floor.core.stair is None:
            continue
        if stair is None:
            stair = floor.core.stair
            continue
        if floor.core.stair.id != stair.id:
            raise ValueError("MVP supports one shared stair id across floors")
    return stair


def _compute_stair_footprint(stair: StairSpec, minor_grid: int) -> StairFootprint:
    """Compute stair geometry (component layout, riser/tread counts) from a StairSpec."""
    width_mm = ceil_to_grid(stair.width, minor_grid)
    width_cells = mm_to_cells(width_mm, minor_grid)
    riser_count = max(2, int(round(stair.floor_height / max(1, stair.riser_pref))))
    tread_count = max(1, riser_count - 1)
    tread_mm = max(1, stair.tread_pref)
    riser_mm = max(1, int(round(stair.floor_height / riser_count)))
    avg_tread_mm = tread_mm

    if stair.type == "straight":
        run_mm = ceil_to_grid(tread_count * tread_mm, minor_grid)
        run_cells = max(1, mm_to_cells(run_mm, minor_grid))
        avg_tread_mm = max(1, int(round(run_mm / tread_count)))
        components = [("flight1", 0, 0, width_cells, run_cells)]
        bbox_w_cells = width_cells
        bbox_h_cells = run_cells
    elif stair.type == "L_landing":
        run1_treads = max(1, int(math.ceil(tread_count / 2)))
        run2_treads = max(1, tread_count - run1_treads)
        run1_mm = ceil_to_grid(run1_treads * tread_mm, minor_grid)
        run2_mm = ceil_to_grid(run2_treads * tread_mm, minor_grid)
        avg_tread_mm = max(1, int(round((run1_mm + run2_mm) / tread_count)))
        run1_cells = max(1, mm_to_cells(run1_mm, minor_grid))
        run2_cells = max(1, mm_to_cells(run2_mm, minor_grid))
        components = [
            ("flight1", 0, 0, run1_cells, width_cells),
            ("landing", run1_cells, 0, width_cells, width_cells),
            ("flight2", run1_cells, width_cells, width_cells, run2_cells),
        ]
        bbox_w_cells = run1_cells + width_cells
        bbox_h_cells = width_cells + run2_cells
    else:
        raise ValueError(f"unsupported stair type '{stair.type}'")

    landing_mm = (width_mm, width_mm)
    return StairFootprint(
        w_cells=bbox_w_cells,
        h_cells=bbox_h_cells,
        components=components,
        riser_count=riser_count,
        tread_count=tread_count,
        riser_mm=riser_mm,
        tread_mm=avg_tread_mm,
        landing_mm=landing_mm,
    )


def _slug(value: str) -> str:
    """Sanitize a string into a lowercase alphanumeric slug for CP-SAT variable naming."""
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value)


def new_rect(
    model: cp_model.CpModel,
    prefix: str,
    max_w: int,
    max_h: int,
    fixed_w: int | None = None,
    fixed_h: int | None = None,
    shared_x: cp_model.IntVar | None = None,
    shared_y: cp_model.IntVar | None = None,
    shared_x_offset: int = 0,
    shared_y_offset: int = 0,
) -> RectVar:
    """Create a RectVar with all necessary CP-SAT variables and constraints."""
    w = (
        model.NewIntVar(fixed_w, fixed_w, f"{prefix}_w")
        if fixed_w is not None
        else model.NewIntVar(1, max_w, f"{prefix}_w")
    )
    h = (
        model.NewIntVar(fixed_h, fixed_h, f"{prefix}_h")
        if fixed_h is not None
        else model.NewIntVar(1, max_h, f"{prefix}_h")
    )

    if shared_x is None:
        x = model.NewIntVar(0, max_w - 1, f"{prefix}_x")
    else:
        x = model.NewIntVar(0, max_w - 1, f"{prefix}_x")
        model.Add(x == shared_x + shared_x_offset)

    if shared_y is None:
        y = model.NewIntVar(0, max_h - 1, f"{prefix}_y")
    else:
        y = model.NewIntVar(0, max_h - 1, f"{prefix}_y")
        model.Add(y == shared_y + shared_y_offset)
    x_end = model.NewIntVar(1, max_w, f"{prefix}_x_end")
    y_end = model.NewIntVar(1, max_h, f"{prefix}_y_end")
    model.Add(x_end == x + w)
    model.Add(y_end == y + h)
    model.Add(x_end <= max_w)
    model.Add(y_end <= max_h)

    area = model.NewIntVar(1, max_w * max_h, f"{prefix}_area")
    model.AddMultiplicationEquality(area, [w, h])

    x_interval = model.NewIntervalVar(x, w, x_end, f"{prefix}_x_interval")
    y_interval = model.NewIntervalVar(y, h, y_end, f"{prefix}_y_interval")
    return RectVar(
        x=x,
        y=y,
        w=w,
        h=h,
        x_end=x_end,
        y_end=y_end,
        area=area,
        x_interval=x_interval,
        y_interval=y_interval,
    )
