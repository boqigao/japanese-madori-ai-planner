from __future__ import annotations

from ortools.sat.python import cp_model

from plan_engine.models import PlanSolution, PlanSpec
from plan_engine.solver.solution_builder import build_solution
from plan_engine.solver.workflow import (
    SolveContext,
    add_floor_packing_constraints,
    add_stair_connection_constraints,
    add_topology_constraints,
    add_wc_ldk_non_adjacent_constraints,
    add_wet_cluster_constraints,
    build_context,
    build_objective,
    create_space_variables,
)


class PlanSolver:
    """Constraint-based floor plan solver using Google OR-Tools CP-SAT."""

    def __init__(self, max_time_seconds: float = 20.0, num_workers: int = 8) -> None:
        """Initialize solver with timeout and worker count."""
        self.max_time_seconds = max_time_seconds
        self.num_workers = num_workers

    def solve(self, spec: PlanSpec) -> PlanSolution:
        """Solve a plan specification and return the solution. Raises RuntimeError if infeasible."""
        ctx = build_context(spec)
        create_space_variables(spec, ctx)
        add_floor_packing_constraints(ctx)
        add_topology_constraints(spec, ctx)
        add_stair_connection_constraints(ctx)
        add_wc_ldk_non_adjacent_constraints(spec, ctx)
        add_wet_cluster_constraints(spec, ctx)
        build_objective(ctx)

        solver, status = self._run_solver(ctx)
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

    def _run_solver(self, ctx: SolveContext) -> tuple[cp_model.CpSolver, int]:
        """Configure and execute the CP-SAT solver. Returns solver and status."""
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.max_time_seconds
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
