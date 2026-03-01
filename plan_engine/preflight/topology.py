from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

from plan_engine.constants import (
    BEDROOM_SPACE_TYPES,
    is_indoor_space_type,
)
from plan_engine.models import BedroomReachabilityViolation
from plan_engine.solver.rect_var import _find_global_stair

if TYPE_CHECKING:
    from plan_engine.models import PlanSpec, ValidationReport


def _check_topology_reachability(
    spec: PlanSpec,
    report: ValidationReport,
) -> list[BedroomReachabilityViolation]:
    """Run reachability checks and detect bedroom-only transit paths.

    The check has two layers:
    1) Generic connectivity: every non-wet node plus each toilet/wc node must
       be reachable from an entry (existing hard preflight check).
    2) Bedroom pass-through guard: bedroom-like rooms are treated as terminal
       nodes and are not allowed to act as intermediate transit nodes.

    Args:
        spec: Parsed plan specification.
        report: Mutable report receiving errors/diagnostics/suggestions.

    Returns:
        A list of structured bedroom reachability violations.
    """
    graph: dict[str, set[str]] = {}
    start_nodes: list[str] = []
    indoor_target_nodes: list[str] = []
    bedroom_nodes: set[str] = set()
    stair_nodes_by_id: dict[str, list[str]] = {}
    floor_space_types: dict[str, dict[str, str]] = {}
    floor_topology_neighbors: dict[str, dict[str, set[str]]] = {}
    outdoor_nodes_by_floor: dict[str, list[str]] = {}

    global_stair = _find_global_stair(spec)
    stair_id = global_stair.id if global_stair is not None else None
    floors_with_stair = set(global_stair.connects.keys()) if global_stair is not None else set()
    if global_stair is not None:
        floors_with_stair.update(fid for fid, floor in spec.floors.items() if floor.core.stair is not None)
        floors_with_stair.intersection_update(spec.floors.keys())

    for floor_id, floor in spec.floors.items():
        floor_space_types[floor_id] = {space.id: space.type for space in floor.spaces}
        local_neighbors: dict[str, set[str]] = {}
        for space in floor.spaces:
            node = f"{floor_id}:{space.id}"
            graph.setdefault(node, set())
            local_neighbors.setdefault(space.id, set())
            if space.type == "entry":
                start_nodes.append(node)
            if is_indoor_space_type(space.type):
                indoor_target_nodes.append(node)
            else:
                outdoor_nodes_by_floor.setdefault(floor_id, []).append(space.id)
            if space.type in BEDROOM_SPACE_TYPES:
                bedroom_nodes.add(node)

        floor_stair_id = floor.core.stair.id if floor.core.stair is not None else stair_id
        if floor_stair_id is not None and floor_id in floors_with_stair:
            stair_node = f"{floor_id}:{floor_stair_id}"
            graph.setdefault(stair_node, set())
            indoor_target_nodes.append(stair_node)
            stair_nodes_by_id.setdefault(floor_stair_id, []).append(stair_node)

        for edge in floor.topology.adjacency:
            left_id, right_id = _edge_ids(edge)
            left = f"{floor_id}:{left_id}"
            right = f"{floor_id}:{right_id}"
            graph.setdefault(left, set()).add(right)
            graph.setdefault(right, set()).add(left)
            local_neighbors.setdefault(left_id, set()).add(right_id)
            local_neighbors.setdefault(right_id, set()).add(left_id)
        floor_topology_neighbors[floor_id] = local_neighbors

    for stair_nodes in stair_nodes_by_id.values():
        for index, node in enumerate(stair_nodes):
            for other in stair_nodes[index + 1 :]:
                graph[node].add(other)
                graph[other].add(node)

    if not start_nodes:
        report.errors.append("preflight: no entry found for topology reachability check")
        return []

    reachable_all, parent_all = _bfs_with_parents(graph, start_nodes, non_transit_nodes=frozenset())
    reachable_no_bed_transit, _ = _bfs_with_parents(graph, start_nodes, non_transit_nodes=bedroom_nodes)

    for node in indoor_target_nodes:
        if node not in reachable_all:
            report.errors.append(f"preflight: topology does not connect entry to '{node}'")

    violations: list[BedroomReachabilityViolation] = []
    for bedroom_node in sorted(bedroom_nodes):
        if bedroom_node not in reachable_all or bedroom_node in reachable_no_bed_transit:
            continue
        path_nodes = _reconstruct_path(parent_all, bedroom_node)
        transit_bedrooms = [node for node in path_nodes[1:-1] if node in bedroom_nodes]
        if not transit_bedrooms:
            continue

        floor_id, bedroom_id = bedroom_node.split(":", 1)
        path_local = tuple(node.split(":", 1)[1] for node in path_nodes)
        transit_local = tuple(node.split(":", 1)[1] for node in transit_bedrooms)
        violations.append(
            BedroomReachabilityViolation(
                floor_id=floor_id,
                bedroom_id=bedroom_id,
                transit_bedroom_ids=transit_local,
                path=path_local,
            )
        )
        report.errors.append(
            f"preflight: {floor_id}:{bedroom_id} is only reachable through bedroom transit "
            f"(path: {' -> '.join(path_local)})"
        )
        report.diagnostics.append(
            f"{floor_id}: blocked bedroom={bedroom_id}, transit_bedrooms={','.join(transit_local)}"
        )
        report.suggestions.append(
            f"Topology fix for {floor_id}:{bedroom_id}: add at least one adjacency to hall/entry/stair-linked circulation "
            "that does not route through another bedroom."
        )

    for floor_id, outdoor_ids in outdoor_nodes_by_floor.items():
        neighbors = floor_topology_neighbors.get(floor_id, {})
        space_types = floor_space_types.get(floor_id, {})
        for outdoor_id in outdoor_ids:
            local_neighbors = neighbors.get(outdoor_id, set())
            indoor_neighbors = [
                candidate_id
                for candidate_id in local_neighbors
                if candidate_id in space_types and is_indoor_space_type(space_types[candidate_id])
            ]
            if indoor_neighbors:
                continue
            report.errors.append(
                f"preflight: {floor_id}:{outdoor_id} outdoor space has no indoor access topology edge"
            )
            report.suggestions.append(
                f"Add topology adjacency like [{outdoor_id}, <indoor_room>, required] on {floor_id}."
            )
    return violations


def _hall_fanout(spec: PlanSpec, floor_id: str) -> int:
    """Return the largest topology fanout among hall spaces on the floor."""
    hall_ids = {space.id for space in spec.floors[floor_id].spaces if space.type == "hall"}
    if not hall_ids:
        return 0
    neighbors: dict[str, set[str]] = {hall_id: set() for hall_id in hall_ids}
    for edge in spec.floors[floor_id].topology.adjacency:
        left_id, right_id = _edge_ids(edge)
        if left_id in neighbors:
            neighbors[left_id].add(right_id)
        if right_id in neighbors:
            neighbors[right_id].add(left_id)
    return max((len(v) for v in neighbors.values()), default=0)


def _bfs_with_parents(
    graph: dict[str, set[str]],
    start_nodes: list[str],
    non_transit_nodes: set[str] | frozenset[str],
) -> tuple[set[str], dict[str, str]]:
    """Run deterministic BFS with optional non-transit node constraints.

    Args:
        graph: Undirected adjacency map keyed by node ID.
        start_nodes: Starting node IDs used as BFS roots.
        non_transit_nodes: Nodes that may be visited as targets but whose
            outgoing edges are not expanded once visited.

    Returns:
        A tuple ``(visited, parent)`` where ``visited`` is the reachable node
        set and ``parent`` maps each discovered node to its predecessor.
    """
    queue: deque[str] = deque(sorted(start_nodes))
    visited: set[str] = set()
    parent: dict[str, str] = {}
    while queue:
        node = queue.popleft()
        if node in visited:
            continue
        visited.add(node)
        if node in non_transit_nodes and node not in start_nodes:
            continue
        for neighbor in sorted(graph.get(node, set())):
            if neighbor not in visited:
                if neighbor not in parent:
                    parent[neighbor] = node
                queue.append(neighbor)
    return visited, parent


def _reconstruct_path(parent: dict[str, str], target: str) -> list[str]:
    """Reconstruct one BFS path from any start node to ``target``.

    Args:
        parent: Parent mapping produced by ``_bfs_with_parents``.
        target: Node whose path should be reconstructed.

    Returns:
        Ordered node list from root to target.
    """
    path = [target]
    cursor = target
    while cursor in parent:
        cursor = parent[cursor]
        path.append(cursor)
    path.reverse()
    return path


def _edge_ids(edge: object) -> tuple[str, str]:
    """Extract ``(left_id, right_id)`` from an adjacency edge object.

    Supports both current tuple-based topology edges and the future structured
    adjacency object format.
    """
    if isinstance(edge, tuple) and len(edge) >= 2:
        return str(edge[0]), str(edge[1])
    left_id = getattr(edge, "left_id", None)
    right_id = getattr(edge, "right_id", None)
    if left_id is None or right_id is None:
        raise ValueError("invalid topology edge")
    return str(left_id), str(right_id)
