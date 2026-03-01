from __future__ import annotations

from typing import TYPE_CHECKING

from ortools.sat.python import cp_model

from plan_engine.solver.rect_var import _compute_stair_footprint, _find_global_stair
from plan_engine.solver.solution_builder import build_solution
from plan_engine.solver.space_specs import _component_count
from plan_engine.solver.workflow import (
    SolveContext,
    add_bath_wash_adjacency_constraints,
    add_closet_parent_constraints,
    add_floor_packing_constraints,
    add_orientation_preference_constraints,
    add_stair_connection_constraints,
    add_toilet_circulation_constraints,
    add_topology_constraints,
    add_wc_ldk_non_adjacent_constraints,
    add_wet_cluster_constraints,
    add_wet_core_circulation_constraints,
    build_context,
    build_objective,
    create_space_variables,
)

if TYPE_CHECKING:
    from plan_engine.models import PlanSolution, PlanSpec


class PlanSolver:
    """Constraint-based floor plan solver using Google OR-Tools CP-SAT."""

    def __init__(self, max_time_seconds: float = 20.0, num_workers: int = 8) -> None:
        """Initialize solver with timeout and worker count."""
        self.max_time_seconds = max_time_seconds
        self.num_workers = num_workers
        self.last_timeout_seconds = max_time_seconds

    def solve(self, spec: PlanSpec) -> PlanSolution:
        """Solve a plan specification and return the solution.

        Args:
            spec: Parsed plan specification to optimize.

        Returns:
            A ``PlanSolution`` when the model is feasible.

        Raises:
            RuntimeError: If CP-SAT cannot find any feasible solution.
        """
        effective_timeout = self._resolve_timeout_seconds(spec)
        ctx = build_context(spec)
        create_space_variables(spec, ctx)
        add_floor_packing_constraints(ctx)
        add_topology_constraints(spec, ctx)
        add_bath_wash_adjacency_constraints(spec, ctx)
        add_toilet_circulation_constraints(spec, ctx)
        add_wet_core_circulation_constraints(spec, ctx)
        add_closet_parent_constraints(spec, ctx)
        add_stair_connection_constraints(ctx)
        add_wc_ldk_non_adjacent_constraints(spec, ctx)
        add_wet_cluster_constraints(spec, ctx)
        add_orientation_preference_constraints(spec, ctx)
        build_objective(ctx)

        solver, status = self._run_solver(ctx, effective_timeout)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            raise RuntimeError(f"unable to produce a valid plan (status={solver.StatusName(status)})")

        return build_solution(
            solver=solver,
            spec=spec,
            placements=ctx.placements,
            stair_spec=ctx.stair_spec,
            stair_footprint=ctx.stair_footprint,
            floor_rank=ctx.floor_rank,
            ordered_floors=ctx.ordered_floors,
        )

    def _run_solver(self, ctx: SolveContext, timeout_seconds: float) -> tuple[cp_model.CpSolver, int]:
        """Configure and execute CP-SAT with the provided timeout.

        Args:
            ctx: Prepared solve context containing model and settings.
            timeout_seconds: Effective time limit for this solve run.

        Returns:
            Tuple ``(solver, status)`` where status is the CP-SAT status code.
        """
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = timeout_seconds
        self.last_timeout_seconds = timeout_seconds
        solver.parameters.num_search_workers = self.num_workers
        if ctx.debug_solver:
            print(
                "debug_solver:",
                f"skip_portal_edge={ctx.skip_portal_edge}",
                f"skip_internal_portal={ctx.skip_internal_portal}",
                f"forced_stair_x_cells={ctx.forced_stair_x_cells}",
                f"forced_stair_y_cells={ctx.forced_stair_y_cells}",
            )
            solver.parameters.log_search_progress = True
        status = solver.Solve(ctx.model)
        return solver, status

    def _resolve_timeout_seconds(self, spec: PlanSpec) -> float:
        """Compute dynamic timeout from model complexity.

        Uses total rectangle component count (rooms + stair components across
        connected floors) to select baseline timeout buckets:
        - ``<=10`` components: 20s
        - ``<=15`` components: 60s
        - ``>15`` components: 120s

        Returns the larger value between this baseline and the user-specified
        ``max_time_seconds``.
        """
        total_components = sum(
            _component_count(space)
            for floor in spec.floors.values()
            for space in floor.spaces
            if space.type != "closet"
        )

        stair = _find_global_stair(spec)
        if stair is not None:
            stair_components = len(_compute_stair_footprint(stair, spec.grid.minor).components)
            floors_with_stair = set(stair.connects.keys())
            floors_with_stair.update(fid for fid, floor in spec.floors.items() if floor.core.stair is not None)
            floors_with_stair.intersection_update(spec.floors.keys())
            total_components += stair_components * len(floors_with_stair)

        if total_components <= 10:
            baseline = 20.0
        elif total_components <= 15:
            baseline = 60.0
        else:
            baseline = 120.0
        return max(self.max_time_seconds, baseline)
