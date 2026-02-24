from __future__ import annotations

from collections import deque

from .constants import WET_SPACE_TYPES
from .models import FloorSolution, PlanSolution, PlanSpec, Rect, ValidationReport


def validate_solution(spec: PlanSpec, solution: PlanSolution) -> ValidationReport:
    report = ValidationReport()
    _validate_space_presence(spec, solution, report)
    _validate_geometry(spec, solution, report)
    _validate_connectivity(solution, report)
    _validate_stair(spec, solution, report)
    return report


def _validate_space_presence(spec: PlanSpec, solution: PlanSolution, report: ValidationReport) -> None:
    for floor_id, floor_spec in spec.floors.items():
        floor_solution = solution.floors.get(floor_id)
        if floor_solution is None:
            report.errors.append(f"missing floor solution for '{floor_id}'")
            continue

        expected_ids = {space.id for space in floor_spec.spaces}
        actual_ids = set(floor_solution.spaces.keys())
        missing = expected_ids - actual_ids
        extra = actual_ids - expected_ids
        if missing:
            report.errors.append(f"{floor_id}: missing spaces {sorted(missing)}")
        if extra:
            report.errors.append(f"{floor_id}: unexpected spaces {sorted(extra)}")

        for space_id, space in floor_solution.spaces.items():
            if not space.rects:
                report.errors.append(f"{floor_id}:{space_id} has no geometry")
                continue
            for rect in space.rects:
                if rect.w <= 0 or rect.h <= 0:
                    report.errors.append(f"{floor_id}:{space_id} has non-positive dimensions")


def _validate_geometry(spec: PlanSpec, solution: PlanSolution, report: ValidationReport) -> None:
    minor = spec.grid.minor
    width = spec.site.envelope.width
    depth = spec.site.envelope.depth

    for floor_id, floor in solution.floors.items():
        all_rects: list[tuple[str, Rect]] = []
        for space in floor.spaces.values():
            for rect in space.rects:
                all_rects.append((space.id, rect))
        if floor.stair is not None:
            for index, component in enumerate(floor.stair.components):
                all_rects.append((f"{floor.stair.id}_component_{index}", component))

        for entity_id, rect in all_rects:
            for value_name, value in (("x", rect.x), ("y", rect.y), ("w", rect.w), ("h", rect.h)):
                if value % minor != 0:
                    report.errors.append(
                        f"{floor_id}:{entity_id} {value_name}={value} is not aligned to {minor}mm grid"
                    )
            if rect.x < 0 or rect.y < 0 or rect.x2 > width or rect.y2 > depth:
                report.errors.append(f"{floor_id}:{entity_id} is outside site envelope")

        for i, (left_id, left_rect) in enumerate(all_rects):
            for right_id, right_rect in all_rects[i + 1 :]:
                if left_rect.overlaps(right_rect):
                    report.errors.append(f"{floor_id}:{left_id} overlaps {right_id}")

        covered_area = sum(rect.area for _, rect in all_rects)
        envelope_area = width * depth
        if covered_area != envelope_area:
            report.errors.append(
                f"{floor_id}: area coverage must be 100% (covered={covered_area}, envelope={envelope_area})"
            )


def _validate_connectivity(solution: PlanSolution, report: ValidationReport) -> None:
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


def _validate_stair(spec: PlanSpec, solution: PlanSolution, report: ValidationReport) -> None:
    stair_specs = [floor.core.stair for floor in spec.floors.values() if floor.core.stair is not None]
    if not stair_specs:
        report.warnings.append("no stair declared")
        return
    stair = stair_specs[0]

    stair_bboxes: list[Rect] = []
    stair_components: list[list[Rect]] = []
    for floor_id, floor in solution.floors.items():
        if floor.stair is None:
            continue
        stair_bboxes.append(floor.stair.bbox)
        stair_components.append(floor.stair.components)
        if floor.stair.id != stair.id:
            report.errors.append(f"{floor_id}: stair id mismatch, expected '{stair.id}'")

    if len(stair_bboxes) >= 2:
        first = stair_bboxes[0]
        for other in stair_bboxes[1:]:
            if other != first:
                report.errors.append("stair projection is not aligned across floors")
                break

    if len(stair_components) >= 2:
        first_components = [(r.x, r.y, r.w, r.h) for r in stair_components[0]]
        for components in stair_components[1:]:
            if [(r.x, r.y, r.w, r.h) for r in components] != first_components:
                report.errors.append("stair components are not aligned across floors")
                break

    for floor_id, hall_id in stair.connects.items():
        floor_solution = solution.floors.get(floor_id)
        if floor_solution is None:
            report.errors.append(f"stair connect floor '{floor_id}' missing in solution")
            continue
        if floor_solution.stair is None:
            report.errors.append(f"stair missing on floor '{floor_id}'")
            continue
        hall = floor_solution.spaces.get(hall_id)
        if hall is None:
            report.errors.append(f"stair hall '{hall_id}' missing on floor '{floor_id}'")
            continue
        if not any(
            component.shares_edge_with(rect)
            for component in floor_solution.stair.components
            for rect in hall.rects
        ):
            report.errors.append(f"stair is not adjacent to hall '{hall_id}' on floor '{floor_id}'")


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
