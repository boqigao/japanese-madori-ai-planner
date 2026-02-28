from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

from plan_engine.constants import is_indoor_space_type, is_outdoor_space_type

if TYPE_CHECKING:
    from plan_engine.models import FloorSolution, PlanSolution, Rect, ValidationReport

TOILET_SPACE_TYPES = frozenset({"toilet", "wc"})
BEDROOM_SPACE_TYPES = frozenset({"bedroom", "master_bedroom"})
CIRCULATION_SPACE_TYPES = frozenset({"hall", "entry"})
WET_CORE_SPACE_TYPES = frozenset({"washroom", "bath"})


def validate_connectivity(solution: PlanSolution, report: ValidationReport) -> None:
    """Validate passable connectivity and WC-LDK separation.

    Connectivity is evaluated over *realized topology edges* only: a topology
    edge is passable when the two entities physically touch on the solved plan.
    This prevents false positives where rooms touch by geometry but no door/topology
    relation exists.
    """
    global_graph: dict[str, set[str]] = {}
    entry_nodes: list[str] = []
    primary_nodes: list[str] = []
    toilet_nodes: list[str] = []
    bedroom_nodes: set[str] = set()
    outdoor_nodes: set[str] = set()

    stair_nodes_by_id: dict[str, list[str]] = {}
    floor_graphs: dict[str, dict[str, set[str]]] = {}

    for floor_id, floor in solution.floors.items():
        graph = _floor_graph_from_realized_topology(floor=floor, floor_id=floor_id, report=report)
        floor_graphs[floor_id] = graph
        for local_node, neighbors in graph.items():
            global_node = f"{floor_id}:{local_node}"
            global_graph.setdefault(global_node, set())
            for neighbor in neighbors:
                global_graph[global_node].add(f"{floor_id}:{neighbor}")

        for space_id, space in floor.spaces.items():
            node = f"{floor_id}:{space_id}"
            if space.type == "entry":
                entry_nodes.append(node)
            if is_indoor_space_type(space.type):
                primary_nodes.append(node)
            elif is_outdoor_space_type(space.type):
                outdoor_nodes.add(node)
            if space.type in TOILET_SPACE_TYPES:
                toilet_nodes.append(node)
            if space.type in BEDROOM_SPACE_TYPES:
                bedroom_nodes.add(node)

        if floor.stair is not None:
            node = f"{floor_id}:{floor.stair.id}"
            stair_nodes_by_id.setdefault(floor.stair.id, []).append(node)
            primary_nodes.append(node)

    for stair_nodes in stair_nodes_by_id.values():
        for i, current in enumerate(stair_nodes):
            for nxt in stair_nodes[i + 1 :]:
                global_graph.setdefault(current, set()).add(nxt)
                global_graph.setdefault(nxt, set()).add(current)

    if not entry_nodes:
        report.errors.append("no entry space found for connectivity validation")
        return

    visited, _ = _bfs_with_parents(global_graph, entry_nodes, non_transit_nodes=outdoor_nodes)
    for node in primary_nodes:
        if node not in visited:
            report.errors.append(f"entry does not reach primary space '{node}'")

    _validate_outdoor_access_realization(solution, floor_graphs, report)
    _validate_toilet_topology_realization(solution, floor_graphs, report)
    _validate_wet_core_topology_realization(solution, floor_graphs, report)
    _validate_toilet_bedroom_pass_through(
        global_graph=global_graph,
        entry_nodes=entry_nodes,
        toilet_nodes=toilet_nodes,
        bedroom_nodes=bedroom_nodes,
        outdoor_nodes=outdoor_nodes,
        report=report,
    )

    for floor_id, floor in solution.floors.items():
        toilets = [sid for sid, s in floor.spaces.items() if s.type in {"toilet", "wc"}]
        ldks = [sid for sid, s in floor.spaces.items() if s.type == "ldk"]
        for wc_id in toilets:
            for ldk_id in ldks:
                wc_rects = floor.spaces[wc_id].rects
                ldk_rects = floor.spaces[ldk_id].rects
                if _entities_touch(wc_rects, ldk_rects):
                    report.errors.append(f"{floor_id}:{wc_id} is directly connected to {ldk_id}")


def _validate_wet_core_topology_realization(
    solution: PlanSolution,
    floor_graphs: dict[str, dict[str, set[str]]],
    report: ValidationReport,
) -> None:
    """Validate wet-core circulation topology declarations and realization.

    Args:
        solution: Solved plan containing per-floor spaces and topology.
        floor_graphs: Realized per-floor adjacency graphs from topology edges.
        report: Mutable validation report to append errors.

    Returns:
        None.
    """
    for floor_id, floor in solution.floors.items():
        wet_core_ids = [
            space_id for space_id, space in floor.spaces.items() if space.type in WET_CORE_SPACE_TYPES
        ]
        if not wet_core_ids:
            continue

        circulation_ids = {
            space_id for space_id, space in floor.spaces.items() if space.type in CIRCULATION_SPACE_TYPES
        }
        if floor.stair is not None:
            circulation_ids.add(floor.stair.id)
        if not circulation_ids:
            report.errors.append(
                f"{floor_id}: wet core exists but no hall/entry/stair circulation entity is present"
            )
            continue

        declared_pairs: list[tuple[str, str]] = []
        for left_id, right_id in floor.topology:
            if left_id in wet_core_ids and right_id in circulation_ids:
                declared_pairs.append((left_id, right_id))
            if right_id in wet_core_ids and left_id in circulation_ids:
                declared_pairs.append((right_id, left_id))

        if not declared_pairs:
            report.errors.append(
                f"{floor_id}: wet core circulation topology is missing "
                "(expected edge from washroom/bath to hall/entry/stair)"
            )
            continue

        floor_graph = floor_graphs.get(floor_id, {})
        realized = False
        for wet_id, circulation_id in declared_pairs:
            if circulation_id in floor_graph.get(wet_id, set()):
                realized = True
                break

        if not realized:
            report.errors.append(
                f"{floor_id}: wet core circulation topology is declared but not physically realized"
            )


def _validate_outdoor_access_realization(
    solution: PlanSolution,
    floor_graphs: dict[str, dict[str, set[str]]],
    report: ValidationReport,
) -> None:
    """Validate declared and realized indoor access for each outdoor space.

    Args:
        solution: Solved plan containing per-floor spaces and topology.
        floor_graphs: Realized per-floor adjacency graphs from topology edges.
        report: Mutable validation report to append errors.

    Returns:
        None.
    """
    for floor_id, floor in solution.floors.items():
        floor_graph = floor_graphs.get(floor_id, {})
        indoor_ids = {
            space_id for space_id, space in floor.spaces.items() if is_indoor_space_type(space.type)
        }
        for outdoor_id, outdoor_space in floor.spaces.items():
            if not is_outdoor_space_type(outdoor_space.type):
                continue
            declared_indoor_neighbors: set[str] = set()
            for left_id, right_id in floor.topology:
                if left_id == outdoor_id and right_id in indoor_ids:
                    declared_indoor_neighbors.add(right_id)
                if right_id == outdoor_id and left_id in indoor_ids:
                    declared_indoor_neighbors.add(left_id)
            if not declared_indoor_neighbors:
                report.errors.append(
                    f"{floor_id}:{outdoor_id} outdoor access topology is missing "
                    "(expected edge to an indoor space)"
                )
                continue
            realized_neighbors = floor_graph.get(outdoor_id, set()).intersection(declared_indoor_neighbors)
            if not realized_neighbors:
                report.errors.append(
                    f"{floor_id}:{outdoor_id} outdoor access topology is declared but not physically realized"
                )


def _validate_toilet_topology_realization(
    solution: PlanSolution,
    floor_graphs: dict[str, dict[str, set[str]]],
    report: ValidationReport,
) -> None:
    """Check toilet circulation topology declarations and realized edges.

    Args:
        solution: Solved plan containing per-floor spaces and topology.
        floor_graphs: Realized per-floor adjacency graphs from topology edges.
        report: Mutable validation report to append errors.

    Returns:
        None.
    """
    for floor_id, floor in solution.floors.items():
        floor_graph = floor_graphs.get(floor_id, {})
        circulation_ids = {
            space_id for space_id, space in floor.spaces.items() if space.type in CIRCULATION_SPACE_TYPES
        }
        if floor.stair is not None:
            circulation_ids.add(floor.stair.id)

        for toilet_id, toilet_space in floor.spaces.items():
            if toilet_space.type not in TOILET_SPACE_TYPES:
                continue
            declared_neighbors: set[str] = set()
            for left_id, right_id in floor.topology:
                if left_id == toilet_id and right_id in circulation_ids:
                    declared_neighbors.add(right_id)
                if right_id == toilet_id and left_id in circulation_ids:
                    declared_neighbors.add(left_id)

            if not declared_neighbors:
                report.errors.append(
                    f"{floor_id}:{toilet_id} toilet circulation topology is missing (expected edge to hall/entry/stair)"
                )
                continue

            realized_neighbors = floor_graph.get(toilet_id, set()).intersection(declared_neighbors)
            if not realized_neighbors:
                report.errors.append(
                    f"{floor_id}:{toilet_id} toilet circulation topology is declared but not physically realized"
                )


def _validate_toilet_bedroom_pass_through(
    global_graph: dict[str, set[str]],
    entry_nodes: list[str],
    toilet_nodes: list[str],
    bedroom_nodes: set[str],
    outdoor_nodes: set[str],
    report: ValidationReport,
) -> None:
    """Reject circulation where toilets are reachable only through bedrooms.

    Args:
        global_graph: Cross-floor passable adjacency graph.
        entry_nodes: Entry nodes used as BFS roots.
        toilet_nodes: Global node IDs for all toilet/WC spaces.
        bedroom_nodes: Global node IDs for all bedroom/master bedroom spaces.
        outdoor_nodes: Global node IDs for balcony/veranda spaces.
        report: Mutable validation report receiving errors.

    Returns:
        None.
    """
    if not toilet_nodes:
        return
    reachable_all, parent_all = _bfs_with_parents(global_graph, entry_nodes, non_transit_nodes=frozenset())
    non_transit_nodes = bedroom_nodes.union(outdoor_nodes)
    reachable_no_bed_transit, _ = _bfs_with_parents(global_graph, entry_nodes, non_transit_nodes=non_transit_nodes)

    for toilet_node in sorted(toilet_nodes):
        if toilet_node not in reachable_all or toilet_node in reachable_no_bed_transit:
            continue
        path_nodes = _reconstruct_path(parent_all, toilet_node)
        transit_bedrooms = [node for node in path_nodes[1:-1] if node in bedroom_nodes]
        if not transit_bedrooms:
            continue
        floor_id, toilet_id = toilet_node.split(":", 1)
        path_local = " -> ".join(node.split(":", 1)[1] for node in path_nodes)
        report.errors.append(
            f"{floor_id}:{toilet_id} toilet is only reachable through bedroom transit (path: {path_local})"
        )


def _floor_graph_from_realized_topology(
    floor: FloorSolution,
    floor_id: str,
    report: ValidationReport,
) -> dict[str, set[str]]:
    """Build passable graph from topology edges that are physically realized.

    Args:
        floor: Solved floor containing geometry and declared topology.
        floor_id: Current floor ID used in warning messages.
        report: Validation report updated with topology realization warnings.

    Returns:
        Undirected graph keyed by entity ID (spaces + stair when present).
    """
    graph: dict[str, set[str]] = {space_id: set() for space_id in floor.spaces}
    if floor.stair is not None:
        graph[floor.stair.id] = set()

    geometry_by_id: dict[str, list[Rect]] = {space.id: space.rects for space in floor.spaces.values()}
    if floor.stair is not None:
        geometry_by_id[floor.stair.id] = floor.stair.components

    for left_id, right_id in floor.topology:
        if left_id not in geometry_by_id or right_id not in geometry_by_id:
            report.warnings.append(
                f"{floor_id}: topology edge {left_id}<->{right_id} references missing solved entity"
            )
            continue
        if _entities_touch(geometry_by_id[left_id], geometry_by_id[right_id]):
            graph[left_id].add(right_id)
            graph[right_id].add(left_id)
        else:
            report.warnings.append(
                f"{floor_id}: topology edge {left_id}<->{right_id} is not physically realized"
            )

    return graph


def _entities_touch(rects_a: list[Rect], rects_b: list[Rect]) -> bool:
    """Check whether any rectangles from two groups share an edge."""
    return any(a.shares_edge_with(b) for a in rects_a for b in rects_b)


def _bfs_with_parents(
    graph: dict[str, set[str]],
    start_nodes: list[str],
    non_transit_nodes: set[str] | frozenset[str],
) -> tuple[set[str], dict[str, str]]:
    """Run deterministic BFS while optionally treating nodes as non-transit.

    Args:
        graph: Undirected graph keyed by global node IDs.
        start_nodes: BFS root nodes.
        non_transit_nodes: Nodes that can be visited but whose outgoing edges
            are not expanded unless they are roots.

    Returns:
        Tuple of ``(visited, parent)`` where ``parent`` stores predecessor links.
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
    """Reconstruct a BFS path from root to target using parent links.

    Args:
        parent: Parent mapping returned by ``_bfs_with_parents``.
        target: Target node to trace back.

    Returns:
        Ordered node list from one root node to ``target``.
    """
    path = [target]
    cursor = target
    while cursor in parent:
        cursor = parent[cursor]
        path.append(cursor)
    path.reverse()
    return path
