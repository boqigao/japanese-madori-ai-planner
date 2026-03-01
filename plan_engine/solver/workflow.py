"""Re-export shim -- public API surface for plan_engine.solver.workflow.

All implementation has moved to sub-modules:
  workflow_context, workflow_spaces, workflow_topology, workflow_wet.
"""

from __future__ import annotations

from plan_engine.solver.workflow_context import (
    SolveContext,
    _constrain_rect_within_buildable_union,
    _create_stair_anchor,
    build_context,
)
from plan_engine.solver.workflow_spaces import (
    _embedded_closet_area_adjustments,
    create_space_variables,
)
from plan_engine.solver.workflow_topology import (
    _resolve_adjacency_strength,
    _space_edge_touch_bool,
    add_floor_packing_constraints,
    add_orientation_preference_constraints,
    add_stair_connection_constraints,
    add_topology_constraints,
    add_wc_ldk_non_adjacent_constraints,
    build_objective,
    resolve_north_south_edges,
)
from plan_engine.solver.workflow_wet import (
    add_bath_wash_adjacency_constraints,
    add_closet_parent_constraints,
    add_toilet_circulation_constraints,
    add_wet_cluster_constraints,
    add_wet_core_circulation_constraints,
)

__all__ = [
    "SolveContext",
    "_constrain_rect_within_buildable_union",
    "_create_stair_anchor",
    "_embedded_closet_area_adjustments",
    "_resolve_adjacency_strength",
    "_space_edge_touch_bool",
    "add_bath_wash_adjacency_constraints",
    "add_closet_parent_constraints",
    "add_floor_packing_constraints",
    "add_orientation_preference_constraints",
    "add_stair_connection_constraints",
    "add_toilet_circulation_constraints",
    "add_topology_constraints",
    "add_wc_ldk_non_adjacent_constraints",
    "add_wet_cluster_constraints",
    "add_wet_core_circulation_constraints",
    "build_context",
    "build_objective",
    "create_space_variables",
    "resolve_north_south_edges",
]
