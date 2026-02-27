from __future__ import annotations

from typing import TYPE_CHECKING

from plan_engine.constants import cells_to_mm
from plan_engine.models import FloorSolution, PlanSolution, PlanSpec, Rect, SpaceGeometry, StairGeometry, StairSpec
from plan_engine.stair_logic import stair_portal_for_floor
from plan_engine.structural import build_structure_report, extract_solution_walls

if TYPE_CHECKING:
    from ortools.sat.python import cp_model

    from plan_engine.solver.rect_var import RectVar, StairFootprint


def build_solution(
    solver: cp_model.CpSolver,
    spec: PlanSpec,
    placements: dict[str, dict[str, list[RectVar]]],
    stair_spec: StairSpec | None,
    stair_footprint: StairFootprint | None,
    floor_rank: dict[str, int],
    ordered_floors: list[str],
) -> PlanSolution:
    """Convert solved CP-SAT variables into a PlanSolution with structural diagnostics.

    Args:
        solver: CP-SAT solver containing selected variable values.
        spec: Parsed plan specification.
        placements: Per-floor/per-entity rectangle variable sets.
        stair_spec: Shared stair specification, when present.
        stair_footprint: Stair footprint metadata in grid cells.
        floor_rank: Floor index mapping for portal direction resolution.
        ordered_floors: Floor IDs in vertical order.

    Returns:
        Immutable solved plan including extracted wall segments and
        structural-report metrics.
    """
    floor_solutions: dict[str, FloorSolution] = {}
    for floor_id, floor in spec.floors.items():
        solved_spaces: dict[str, SpaceGeometry] = {}
        for space in floor.spaces:
            rects = [
                Rect(
                    x=cells_to_mm(solver.Value(rect.x), spec.grid.minor),
                    y=cells_to_mm(solver.Value(rect.y), spec.grid.minor),
                    w=cells_to_mm(solver.Value(rect.w), spec.grid.minor),
                    h=cells_to_mm(solver.Value(rect.h), spec.grid.minor),
                )
                for rect in placements[floor_id][space.id]
            ]
            solved_spaces[space.id] = SpaceGeometry(id=space.id, type=space.type, rects=rects)

        stair_geometry = None
        if stair_spec is not None and stair_spec.id in placements[floor_id] and stair_footprint is not None:
            stair_components = [
                Rect(
                    x=cells_to_mm(solver.Value(rect.x), spec.grid.minor),
                    y=cells_to_mm(solver.Value(rect.y), spec.grid.minor),
                    w=cells_to_mm(solver.Value(rect.w), spec.grid.minor),
                    h=cells_to_mm(solver.Value(rect.h), spec.grid.minor),
                )
                for rect in placements[floor_id][stair_spec.id]
            ]
            min_x = min(component.x for component in stair_components)
            min_y = min(component.y for component in stair_components)
            max_x = max(component.x2 for component in stair_components)
            max_y = max(component.y2 for component in stair_components)
            portal = stair_portal_for_floor(
                stair_type=stair_spec.type,
                floor_index=floor_rank[floor_id],
                floor_count=len(ordered_floors),
                component_count=len(stair_components),
            )
            stair_geometry = StairGeometry(
                id=stair_spec.id,
                type=stair_spec.type,
                bbox=Rect(
                    x=min_x,
                    y=min_y,
                    w=max_x - min_x,
                    h=max_y - min_y,
                ),
                components=stair_components,
                floor_height=stair_spec.floor_height,
                riser_count=stair_footprint.riser_count,
                tread_count=stair_footprint.tread_count,
                riser_mm=stair_footprint.riser_mm,
                tread_mm=stair_footprint.tread_mm,
                landing_size=stair_footprint.landing_mm,
                connects=stair_spec.connects,
                portal_component=portal.component_index,
                portal_edge=portal.edge,
            )

        floor_solutions[floor_id] = FloorSolution(
            id=floor_id,
            spaces=solved_spaces,
            stair=stair_geometry,
            topology=[edge.to_tuple() for edge in floor.topology.adjacency],
        )

    base_solution = PlanSolution(
        units=spec.units,
        grid=spec.grid,
        envelope=spec.site.envelope,
        north=spec.site.north,
        floors=floor_solutions,
    )
    walls_by_floor = extract_solution_walls(base_solution)
    structure_report = build_structure_report(
        solution=base_solution,
        walls_by_floor=walls_by_floor,
        direct_below_target=0.5,
        wall_balance_target=0.5,
    )
    return PlanSolution(
        units=spec.units,
        grid=spec.grid,
        envelope=spec.site.envelope,
        north=spec.site.north,
        floors=floor_solutions,
        walls=walls_by_floor,
        structure_report=structure_report,
    )
