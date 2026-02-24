from __future__ import annotations

from collections import deque

from plan_engine.constants import WET_SPACE_TYPES
from plan_engine.models import FloorSolution, PlanSolution, Rect, ValidationReport


def validate_connectivity(solution: PlanSolution, report: ValidationReport) -> None:
    global_graph: dict[str, set[str]] = {}
    entry_nodes: list[str] = []
    primary_nodes: list[str] = []

    stair_nodes_by_id: dict[str, list[str]] = {}
    floor_graphs: dict[str, dict[str, set[str]]] = {}

    for floor_id, floor in solution.floors.items():
        graph = _floor_graph(floor)
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
            if space.type not in WET_SPACE_TYPES:
                primary_nodes.append(node)

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

    visited = _bfs(global_graph, entry_nodes)
    for node in primary_nodes:
        if node not in visited:
            report.errors.append(f"entry does not reach primary space '{node}'")

    for floor_id, floor in solution.floors.items():
        graph = floor_graphs[floor_id]
        toilets = [sid for sid, s in floor.spaces.items() if s.type in {"toilet", "wc"}]
        ldks = [sid for sid, s in floor.spaces.items() if s.type == "ldk"]
        for wc_id in toilets:
            for ldk_id in ldks:
                if ldk_id in graph.get(wc_id, set()):
                    report.errors.append(f"{floor_id}:{wc_id} is directly connected to {ldk_id}")


def _floor_graph(floor: FloorSolution) -> dict[str, set[str]]:
    graph: dict[str, set[str]] = {space_id: set() for space_id in floor.spaces}
    if floor.stair is not None:
        graph[floor.stair.id] = set()

    nodes: list[tuple[str, list[Rect]]] = [(space.id, space.rects) for space in floor.spaces.values()]
    if floor.stair is not None:
        nodes.append((floor.stair.id, floor.stair.components))

    for i, (left_id, left_rects) in enumerate(nodes):
        for right_id, right_rects in nodes[i + 1 :]:
            if _entities_touch(left_rects, right_rects):
                graph[left_id].add(right_id)
                graph[right_id].add(left_id)

    return graph


def _entities_touch(rects_a: list[Rect], rects_b: list[Rect]) -> bool:
    return any(a.shares_edge_with(b) for a in rects_a for b in rects_b)


def _bfs(graph: dict[str, set[str]], start_nodes: list[str]) -> set[str]:
    visited: set[str] = set()
    queue: deque[str] = deque(start_nodes)
    while queue:
        node = queue.popleft()
        if node in visited:
            continue
        visited.add(node)
        for neighbor in graph.get(node, set()):
            if neighbor not in visited:
                queue.append(neighbor)
    return visited
