from __future__ import annotations

from collections import deque

from .constants import WET_SPACE_TYPES
from .models import FloorSolution, PlanSolution, PlanSpec, Rect, ValidationReport
from .stair_logic import ordered_floor_ids, stair_portal_for_floor


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
    ordered_floors = ordered_floor_ids(solution.floors.keys())
    floor_rank = {floor_id: idx for idx, floor_id in enumerate(ordered_floors)}

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
        portal = stair_portal_for_floor(
            stair_type=stair.type,
            floor_index=floor_rank.get(floor_id, 0),
            floor_count=len(ordered_floors),
            component_count=len(floor_solution.stair.components),
        )
        if floor_solution.stair.portal_component is not None and floor_solution.stair.portal_component != portal.component_index:
            report.errors.append(
                f"{floor_id}: stair portal component mismatch (expected {portal.component_index}, got {floor_solution.stair.portal_component})"
            )
        if floor_solution.stair.portal_edge is not None and floor_solution.stair.portal_edge != portal.edge:
            report.errors.append(
                f"{floor_id}: stair portal edge mismatch (expected {portal.edge}, got {floor_solution.stair.portal_edge})"
            )

        portal_component = floor_solution.stair.components[portal.component_index]
        _validate_portal_internal(
            floor_id=floor_id,
            component=portal_component,
            edge=portal.edge,
            width=spec.site.envelope.width,
            depth=spec.site.envelope.depth,
            report=report,
        )

        segments = _shared_segments_on_portal_edge(portal_component, hall.rects, portal.edge)
        unique_segments = {_segment_key(segment) for segment in segments}
        if len(unique_segments) != 1:
            report.errors.append(
                f"{floor_id}: stair must connect hall '{hall_id}' through exactly one portal edge ({portal.edge})"
            )
            continue
        if _segment_length(next(iter(unique_segments))) < spec.grid.minor:
            report.errors.append(f"{floor_id}: stair portal width is below one minor grid")

        is_top_floor = floor_rank.get(floor_id, 0) == len(ordered_floors) - 1
        if is_top_floor:
            for index, component in enumerate(floor_solution.stair.components):
                if index == portal.component_index:
                    continue
                if any(component.shares_edge_with(rect) for rect in hall.rects):
                    report.errors.append(
                        f"{floor_id}: hall '{hall_id}' touches non-portal stair component {index}"
                    )


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


def _shared_segments_on_portal_edge(
    portal_component: Rect,
    hall_rects: list[Rect],
    edge: str,
) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    segments: list[tuple[tuple[int, int], tuple[int, int]]] = []
    for hall_rect in hall_rects:
        segment = _edge_shared_segment(portal_component, hall_rect, edge)
        if segment is not None:
            segments.append(segment)
    return segments


def _segment_key(
    segment: tuple[tuple[int, int], tuple[int, int]]
) -> tuple[tuple[int, int], tuple[int, int]]:
    p1, p2 = segment
    if p1 <= p2:
        return p1, p2
    return p2, p1


def _segment_length(segment: tuple[tuple[int, int], tuple[int, int]]) -> int:
    p1, p2 = segment
    return abs(p2[0] - p1[0]) + abs(p2[1] - p1[1])


def _edge_shared_segment(
    portal_component: Rect,
    other: Rect,
    edge: str,
) -> tuple[tuple[int, int], tuple[int, int]] | None:
    if edge == "left":
        if other.x2 != portal_component.x:
            return None
        y1 = max(portal_component.y, other.y)
        y2 = min(portal_component.y2, other.y2)
        return ((portal_component.x, y1), (portal_component.x, y2)) if y2 > y1 else None
    if edge == "right":
        if other.x != portal_component.x2:
            return None
        y1 = max(portal_component.y, other.y)
        y2 = min(portal_component.y2, other.y2)
        return ((portal_component.x2, y1), (portal_component.x2, y2)) if y2 > y1 else None
    if edge == "top":
        if other.y2 != portal_component.y:
            return None
        x1 = max(portal_component.x, other.x)
        x2 = min(portal_component.x2, other.x2)
        return ((x1, portal_component.y), (x2, portal_component.y)) if x2 > x1 else None
    if edge == "bottom":
        if other.y != portal_component.y2:
            return None
        x1 = max(portal_component.x, other.x)
        x2 = min(portal_component.x2, other.x2)
        return ((x1, portal_component.y2), (x2, portal_component.y2)) if x2 > x1 else None
    return None


def _validate_portal_internal(
    floor_id: str,
    component: Rect,
    edge: str,
    width: int,
    depth: int,
    report: ValidationReport,
) -> None:
    if edge == "left" and component.x <= 0:
        report.errors.append(f"{floor_id}: stair portal edge left is on exterior boundary")
    elif edge == "right" and component.x2 >= width:
        report.errors.append(f"{floor_id}: stair portal edge right is on exterior boundary")
    elif edge == "top" and component.y <= 0:
        report.errors.append(f"{floor_id}: stair portal edge top is on exterior boundary")
    elif edge == "bottom" and component.y2 >= depth:
        report.errors.append(f"{floor_id}: stair portal edge bottom is on exterior boundary")


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
