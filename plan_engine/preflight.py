from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING

from plan_engine.constants import (
    WET_MODULE_SIZES_MM,
    is_indoor_space_type,
    mm_to_cells,
)
from plan_engine.models import BedroomReachabilityViolation, ValidationReport
from plan_engine.solver.rect_var import _compute_stair_footprint, _find_global_stair
from plan_engine.solver.space_specs import _max_area_cells, _min_area_cells, _target_area_cells

if TYPE_CHECKING:
    from plan_engine.models import PlanSpec, SpaceSpec

BEDROOM_SPACE_TYPES = frozenset({"bedroom", "master_bedroom"})
TOILET_SPACE_TYPES = frozenset({"toilet", "wc"})
WET_CORE_SPACE_TYPES = frozenset({"washroom", "bath"})
CIRCULATION_SPACE_TYPES = frozenset({"hall", "entry"})


@dataclass(frozen=True)
class FloorPreflightStats:
    """Numeric preflight summary for one floor.

    Attributes:
        floor_id: Floor identifier (for example ``F1``).
        envelope_cells: Total available cells in the rectangular envelope.
        buildable_cells: Total indoor buildable cells on this floor.
        min_cells: Sum of required minimum area cells for all entities.
        max_cells: Sum of available maximum area cells for all entities.
        room_count: Number of spaces declared on the floor.
        hall_fanout: Maximum number of topology neighbors connected to any hall.
    """

    floor_id: str
    envelope_cells: int
    buildable_cells: int
    min_cells: int
    max_cells: int
    room_count: int
    hall_fanout: int


@dataclass(frozen=True)
class PreflightResult:
    """Result bundle returned by preflight checks.

    Attributes:
        report: Collected errors, warnings, diagnostics, and suggestions.
        floor_stats: Per-floor numeric summaries reused for solver-failure diagnostics.
        bedroom_violations: Bedroom pass-through circulation violations detected
            during preflight topology checks.
    """

    report: ValidationReport
    floor_stats: dict[str, FloorPreflightStats]
    bedroom_violations: tuple[BedroomReachabilityViolation, ...] = ()


def run_preflight(spec: PlanSpec) -> PreflightResult:
    """Run deterministic feasibility checks before CP-SAT solving.

    Args:
        spec: Parsed plan specification.

    Returns:
        ``PreflightResult`` containing both user-facing report messages and
        per-floor numeric summaries.
    """
    report = ValidationReport()
    floor_stats: dict[str, FloorPreflightStats] = {}

    minor = spec.grid.minor
    envelope_w = mm_to_cells(spec.site.envelope.width, minor)
    envelope_h = mm_to_cells(spec.site.envelope.depth, minor)
    envelope_area = envelope_w * envelope_h

    _check_envelope_alignment(spec, report)
    stair_cells_by_floor = _stair_area_by_floor(spec, report, envelope_w, envelope_h)
    _check_reference_consistency(spec, report)

    for floor_id, floor in spec.floors.items():
        buildable_area = _check_buildable_mask_consistency(
            spec=spec,
            floor_id=floor_id,
            envelope_w_cells=envelope_w,
            envelope_h_cells=envelope_h,
            report=report,
        )
        min_cells, max_cells = _floor_area_budget(
            spec=spec,
            floor_id=floor_id,
            buildable_area=buildable_area,
            stair_cells=stair_cells_by_floor.get(floor_id, 0),
        )
        hall_fanout = _hall_fanout(spec, floor_id)
        floor_stats[floor_id] = FloorPreflightStats(
            floor_id=floor_id,
            envelope_cells=envelope_area,
            buildable_cells=buildable_area,
            min_cells=min_cells,
            max_cells=max_cells,
            room_count=len(floor.spaces),
            hall_fanout=hall_fanout,
        )

        if min_cells > buildable_area:
            over_cells = min_cells - buildable_area
            report.errors.append(
                f"preflight: {floor_id} minimum indoor area exceeds buildable area by {over_cells} cells "
                f"({cells_to_sqm(over_cells, minor):.1f}sqm)"
            )
            _suggest_reduce_large_targets(spec, floor_id, report)
        if max_cells < buildable_area:
            gap_cells = buildable_area - max_cells
            report.errors.append(
                f"preflight: {floor_id} maximum indoor area cannot fill buildable area, short by {gap_cells} cells "
                f"({cells_to_sqm(gap_cells, minor):.1f}sqm)"
            )
            report.suggestions.append(
                f"Increase indoor target areas or add an indoor storage/hall room on {floor_id} to absorb about "
                f"{cells_to_sqm(gap_cells, minor):.1f}sqm."
            )

        _check_room_min_width(spec, floor_id, envelope_w, envelope_h, report)
        _check_toilet_circulation_topology(spec, floor_id, report)
        _check_wet_core_circulation_topology(spec, floor_id, report)
        _check_wet_cluster_fit(spec, floor_id, envelope_w, envelope_h, report)

        if hall_fanout >= 8:
            report.warnings.append(
                f"preflight: {floor_id} hall adjacency fanout is {hall_fanout} (>=8), "
                "this often makes solving harder"
            )

        report.diagnostics.append(
            f"{floor_id}: envelope={envelope_area} cells, buildable={buildable_area} cells, "
            f"min={min_cells}, max={max_cells}, "
            f"rooms={len(floor.spaces)}, hall_fanout={hall_fanout}"
        )

    bedroom_violations = _check_topology_reachability(spec, report)
    return PreflightResult(
        report=report,
        floor_stats=floor_stats,
        bedroom_violations=tuple(bedroom_violations),
    )


def build_solver_failure_report(
    base_warnings: list[str],
    error_message: str,
    floor_stats: dict[str, FloorPreflightStats],
    timeout_seconds: float,
) -> ValidationReport:
    """Create a solver-failure report with actionable diagnostics.

    Args:
        base_warnings: Warnings to preserve (usually from preflight).
        error_message: Final solver exception message.
        floor_stats: Per-floor preflight numeric summaries.
        timeout_seconds: Effective timeout used by the solver.

    Returns:
        A populated ``ValidationReport`` suitable for ``report.txt`` output.
    """
    report = ValidationReport(
        errors=[f"solve_failed: {error_message}"],
        warnings=list(base_warnings),
    )
    for floor_id in sorted(floor_stats):
        stats = floor_stats[floor_id]
        min_slack = stats.buildable_cells - stats.min_cells
        max_slack = stats.max_cells - stats.buildable_cells
        report.diagnostics.append(
            f"{floor_id}: buildable={stats.buildable_cells} cells, "
            f"min_slack={min_slack} cells, max_slack={max_slack} cells, "
            f"rooms={stats.room_count}, hall_fanout={stats.hall_fanout}"
        )
    report.suggestions.append(
        f"Increase solver timeout (current effective timeout={timeout_seconds:.0f}s) for complex cases."
    )
    for floor_id in sorted(floor_stats):
        stats = floor_stats[floor_id]
        if stats.hall_fanout >= 7:
            report.suggestions.append(
                f"Reduce {floor_id} hall adjacency fanout from {stats.hall_fanout} to <=6."
            )
    report.suggestions.append("Simplify hall shape/component count when using multi-rectangle hall.")
    return report


def _stair_area_by_floor(
    spec: PlanSpec,
    report: ValidationReport,
    envelope_w: int,
    envelope_h: int,
) -> dict[str, int]:
    """Calculate stair footprint area contribution for each floor using the shared stair definition."""
    stair = _find_global_stair(spec)
    if stair is None:
        return {}

    footprint = _compute_stair_footprint(stair, spec.grid.minor)
    if footprint.w_cells > envelope_w or footprint.h_cells > envelope_h:
        report.errors.append(
            "preflight: stair footprint does not fit envelope "
            f"(needs {footprint.w_cells}x{footprint.h_cells} cells, envelope is {envelope_w}x{envelope_h})"
        )

    floors_with_stair = set(stair.connects.keys())
    floors_with_stair.update(fid for fid, floor in spec.floors.items() if floor.core.stair is not None)
    floors_with_stair.intersection_update(spec.floors.keys())
    stair_area = sum(component[3] * component[4] for component in footprint.components)
    return {floor_id: stair_area for floor_id in floors_with_stair}


def _floor_area_budget(
    spec: PlanSpec,
    floor_id: str,
    buildable_area: int,
    stair_cells: int,
) -> tuple[int, int]:
    """Return ``(min_cells, max_cells)`` for indoor coverage on one floor.

    Outdoor spaces are excluded from indoor buildable fill accounting.
    """
    floor = spec.floors[floor_id]
    min_cells = stair_cells
    max_cells = stair_cells
    for space in floor.spaces:
        if not is_indoor_space_type(space.type):
            continue
        fixed = WET_MODULE_SIZES_MM.get(space.type)
        if fixed is not None:
            area = mm_to_cells(fixed[0], spec.grid.minor) * mm_to_cells(fixed[1], spec.grid.minor)
            min_cells += area
            max_cells += area
            continue

        min_cells += _min_area_cells(space, spec.grid.minor)
        max_area = _max_area_cells(space, spec.grid.minor)
        max_cells += buildable_area if max_area is None else max_area
    return min_cells, max_cells


def _check_envelope_alignment(spec: PlanSpec, report: ValidationReport) -> None:
    """Verify site envelope aligns to the minor grid (defensive duplicate check)."""
    if spec.site.envelope.width % spec.grid.minor != 0 or spec.site.envelope.depth % spec.grid.minor != 0:
        report.errors.append(
            "preflight: envelope width/depth must align to minor grid "
            f"({spec.grid.minor}mm)"
        )


def _check_room_min_width(
    spec: PlanSpec,
    floor_id: str,
    envelope_w: int,
    envelope_h: int,
    report: ValidationReport,
) -> None:
    """Ensure each room minimum width can physically fit within envelope short edge."""
    short_edge_cells = min(envelope_w, envelope_h)
    short_edge_mm = short_edge_cells * spec.grid.minor
    for space in spec.floors[floor_id].spaces:
        min_width = space.size_constraints.min_width
        if min_width is None:
            continue
        width_cells = mm_to_cells(min_width, spec.grid.minor)
        if width_cells > short_edge_cells:
            report.errors.append(
                f"preflight: {floor_id}:{space.id} min_width={min_width}mm exceeds envelope short side "
                f"({short_edge_mm}mm)"
            )


def _check_buildable_mask_consistency(
    spec: PlanSpec,
    floor_id: str,
    envelope_w_cells: int,
    envelope_h_cells: int,
    report: ValidationReport,
) -> int:
    """Validate one floor buildable mask and return its area in cells.

    Args:
        spec: Parsed plan specification.
        floor_id: Floor identifier.
        envelope_w_cells: Envelope width in cells.
        envelope_h_cells: Envelope depth in cells.
        report: Mutable validation report for preflight findings.

    Returns:
        Buildable indoor area in grid cells. Falls back to full envelope area
        when parsing/validation errors make the mask unusable.
    """
    floor = spec.floors[floor_id]
    envelope_w_mm = envelope_w_cells * spec.grid.minor
    envelope_h_mm = envelope_h_cells * spec.grid.minor
    rects = list(floor.buildable_mask)
    if not rects:
        return envelope_w_cells * envelope_h_cells

    total_cells = 0
    for index, rect in enumerate(rects):
        if rect.w <= 0 or rect.h <= 0:
            report.errors.append(f"preflight: {floor_id} buildable rect #{index} has non-positive size")
            continue
        aligned = True
        for field_name, value in (("x", rect.x), ("y", rect.y), ("w", rect.w), ("h", rect.h)):
            if value % spec.grid.minor != 0:
                aligned = False
                report.errors.append(
                    f"preflight: {floor_id} buildable rect #{index} field '{field_name}'={value} "
                    f"is not aligned to {spec.grid.minor}mm"
                )
        if rect.x < 0 or rect.y < 0 or rect.x + rect.w > envelope_w_mm or rect.y + rect.h > envelope_h_mm:
            report.errors.append(
                f"preflight: {floor_id} buildable rect #{index} is outside envelope "
                f"({envelope_w_mm}x{envelope_h_mm}mm)"
            )
        if aligned:
            total_cells += mm_to_cells(rect.w, spec.grid.minor) * mm_to_cells(rect.h, spec.grid.minor)

    for i, left in enumerate(rects):
        for right in rects[i + 1 :]:
            if _rects_overlap(left.x, left.y, left.w, left.h, right.x, right.y, right.w, right.h):
                report.errors.append(f"preflight: {floor_id} buildable mask rectangles must not overlap")
                break

    if total_cells <= 0:
        report.errors.append(f"preflight: {floor_id} buildable mask has zero indoor area")
        return envelope_w_cells * envelope_h_cells
    return total_cells


def _check_reference_consistency(spec: PlanSpec, report: ValidationReport) -> None:
    """Validate adjacency and stair references point to declared floor entities."""
    global_stair = _find_global_stair(spec)
    stair_id = global_stair.id if global_stair is not None else None

    for floor_id, floor in spec.floors.items():
        space_ids = {space.id for space in floor.spaces}
        floor_stair_id = floor.core.stair.id if floor.core.stair is not None else stair_id
        valid_ids = set(space_ids)
        if floor_stair_id is not None:
            valid_ids.add(floor_stair_id)

        for edge in floor.topology.adjacency:
            left_id, right_id = _edge_ids(edge)
            if left_id not in valid_ids:
                report.errors.append(f"preflight: {floor_id} adjacency references unknown id '{left_id}'")
            if right_id not in valid_ids:
                report.errors.append(f"preflight: {floor_id} adjacency references unknown id '{right_id}'")

    if global_stair is None:
        return
    for floor_id, hall_id in global_stair.connects.items():
        if floor_id not in spec.floors:
            report.errors.append(f"preflight: stair connects references unknown floor '{floor_id}'")
            continue
        hall_map = {space.id: space.type for space in spec.floors[floor_id].spaces}
        if hall_id not in hall_map:
            report.errors.append(f"preflight: stair connects references unknown space '{hall_id}' on {floor_id}")
            continue
        if hall_map[hall_id] != "hall":
            report.errors.append(f"preflight: stair connect target '{hall_id}' on {floor_id} must be type hall")


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


def _check_wet_cluster_fit(
    spec: PlanSpec,
    floor_id: str,
    envelope_w: int,
    envelope_h: int,
    report: ValidationReport,
) -> None:
    """Check wet-module dimensions fit and wet-core modules can be connected.

    The wet core is defined as washroom+bath modules. Toilet/WC modules are
    validated for independent fit but are not forced into the wet-core packing
    cluster at preflight stage.
    """
    floor = spec.floors[floor_id]
    wet_core_modules: list[tuple[int, int]] = []
    for space in floor.spaces:
        dims = WET_MODULE_SIZES_MM.get(space.type)
        if dims is None:
            continue
        w_cells = mm_to_cells(dims[0], spec.grid.minor)
        h_cells = mm_to_cells(dims[1], spec.grid.minor)
        if space.type in WET_CORE_SPACE_TYPES:
            wet_core_modules.append((w_cells, h_cells))
        if w_cells > envelope_w or h_cells > envelope_h:
            report.errors.append(
                f"preflight: {floor_id}:{space.id} wet module {dims[0]}x{dims[1]}mm "
                f"does not fit envelope {envelope_w * spec.grid.minor}x{envelope_h * spec.grid.minor}mm"
            )

    if len(wet_core_modules) <= 1:
        return
    if not _can_pack_connected_wet_modules(wet_core_modules, envelope_w, envelope_h):
        report.errors.append(
            f"preflight: {floor_id} washroom+bath wet core cannot form a connected cluster inside envelope"
        )


def _check_toilet_circulation_topology(spec: PlanSpec, floor_id: str, report: ValidationReport) -> None:
    """Validate that each toilet/wc has declared circulation adjacency edges.

    Args:
        spec: Parsed plan specification.
        floor_id: Floor identifier to validate.
        report: Mutable report receiving errors and suggestions.

    Returns:
        None.
    """
    floor = spec.floors[floor_id]
    space_type_by_id = {space.id: space.type for space in floor.spaces}
    toilet_ids = [space_id for space_id, space_type in space_type_by_id.items() if space_type in TOILET_SPACE_TYPES]
    if not toilet_ids:
        return

    global_stair = _find_global_stair(spec)
    floor_stair_id = floor.core.stair.id if floor.core.stair is not None else global_stair.id if global_stair else None
    has_floor_stair = floor.core.stair is not None or (global_stair is not None and floor_id in global_stair.connects)

    circulation_ids = {
        space_id for space_id, space_type in space_type_by_id.items() if space_type in CIRCULATION_SPACE_TYPES
    }
    if has_floor_stair and floor_stair_id is not None:
        circulation_ids.add(floor_stair_id)

    if not circulation_ids:
        report.errors.append(
            f"preflight: {floor_id} defines toilet/wc but has no hall/entry/stair circulation node"
        )
        return

    neighbor_map: dict[str, set[str]] = {toilet_id: set() for toilet_id in toilet_ids}
    for edge in floor.topology.adjacency:
        left_id, right_id = _edge_ids(edge)
        if left_id in neighbor_map:
            neighbor_map[left_id].add(right_id)
        if right_id in neighbor_map:
            neighbor_map[right_id].add(left_id)

    for toilet_id in toilet_ids:
        if any(neighbor in circulation_ids for neighbor in neighbor_map[toilet_id]):
            continue
        report.errors.append(
            f"preflight: {floor_id}:{toilet_id} has no circulation topology edge to hall/entry/stair"
        )
        report.suggestions.append(
            f"Add topology adjacency like [{toilet_id}, <hall_or_entry_or_stair>, required] on {floor_id}."
        )


def _check_wet_core_circulation_topology(spec: PlanSpec, floor_id: str, report: ValidationReport) -> None:
    """Validate wet-core topology has at least one circulation connection.

    Args:
        spec: Parsed plan specification.
        floor_id: Floor identifier to validate.
        report: Mutable report receiving errors and suggestions.

    Returns:
        None.
    """
    floor = spec.floors[floor_id]
    space_type_by_id = {space.id: space.type for space in floor.spaces}
    wet_core_ids = [
        space_id
        for space_id, space_type in space_type_by_id.items()
        if space_type in WET_CORE_SPACE_TYPES
    ]
    if not wet_core_ids:
        return

    global_stair = _find_global_stair(spec)
    floor_stair_id = floor.core.stair.id if floor.core.stair is not None else global_stair.id if global_stair else None
    has_floor_stair = floor.core.stair is not None or (global_stair is not None and floor_id in global_stair.connects)

    circulation_ids = {
        space_id for space_id, space_type in space_type_by_id.items() if space_type in CIRCULATION_SPACE_TYPES
    }
    if has_floor_stair and floor_stair_id is not None:
        circulation_ids.add(floor_stair_id)

    if not circulation_ids:
        report.errors.append(
            f"preflight: {floor_id} defines wet core but has no hall/entry/stair circulation node"
        )
        return

    has_wet_core_circulation_edge = False
    for edge in floor.topology.adjacency:
        left_id, right_id = _edge_ids(edge)
        left_is_wet = left_id in wet_core_ids
        right_is_wet = right_id in wet_core_ids
        if (left_is_wet and right_id in circulation_ids) or (right_is_wet and left_id in circulation_ids):
            has_wet_core_circulation_edge = True
            break

    if has_wet_core_circulation_edge:
        return

    report.errors.append(
        f"preflight: {floor_id} wet core has no circulation topology edge to hall/entry/stair"
    )
    report.suggestions.append(
        "Add at least one topology adjacency like "
        f"[<wash_or_bath>, <hall_or_entry_or_stair>, required] on {floor_id}."
    )


def _can_pack_connected_wet_modules(
    modules: list[tuple[int, int]],
    envelope_w: int,
    envelope_h: int,
) -> bool:
    """Return True when fixed-size wet modules can be arranged as one connected cluster.

    This is a small deterministic search over grid-aligned placements. It is
    only used for early rejection and runs on tiny module counts.
    """
    modules = sorted(modules, reverse=True)
    placed: list[tuple[int, int, int, int]] = []
    seen_states: set[tuple[tuple[int, int, int, int], ...]] = set()

    def normalize(rects: list[tuple[int, int, int, int]]) -> tuple[tuple[int, int, int, int], ...]:
        min_x = min(r[0] for r in rects)
        min_y = min(r[1] for r in rects)
        normalized = sorted((x - min_x, y - min_y, w, h) for x, y, w, h in rects)
        return tuple(normalized)

    def bbox(rects: list[tuple[int, int, int, int]]) -> tuple[int, int]:
        min_x = min(r[0] for r in rects)
        min_y = min(r[1] for r in rects)
        max_x = max(r[0] + r[2] for r in rects)
        max_y = max(r[1] + r[3] for r in rects)
        return max_x - min_x, max_y - min_y

    def overlaps(rect: tuple[int, int, int, int], others: list[tuple[int, int, int, int]]) -> bool:
        rx, ry, rw, rh = rect
        for ox, oy, ow, oh in others:
            if not (rx + rw <= ox or ox + ow <= rx or ry + rh <= oy or oy + oh <= ry):
                return True
        return False

    def candidate_positions(module: tuple[int, int]) -> list[tuple[int, int]]:
        if not placed:
            return [(0, 0)]
        w, h = module
        positions: set[tuple[int, int]] = set()
        for px, py, pw, ph in placed:
            # Left/right touching candidates.
            for y in range(py - h + 1, py + ph):
                positions.add((px - w, y))
                positions.add((px + pw, y))
            # Top/bottom touching candidates.
            for x in range(px - w + 1, px + pw):
                positions.add((x, py - h))
                positions.add((x, py + ph))
        return list(positions)

    def dfs(index: int) -> bool:
        if index == len(modules):
            bw, bh = bbox(placed)
            return bw <= envelope_w and bh <= envelope_h

        module = modules[index]
        for x, y in candidate_positions(module):
            rect = (x, y, module[0], module[1])
            if overlaps(rect, placed):
                continue
            trial = placed + [rect]
            bw, bh = bbox(trial)
            if bw > envelope_w or bh > envelope_h:
                continue
            state = normalize(trial)
            if state in seen_states:
                continue
            seen_states.add(state)
            placed.append(rect)
            if dfs(index + 1):
                return True
            placed.pop()
        return False

    return dfs(0)


def _suggest_reduce_large_targets(spec: PlanSpec, floor_id: str, report: ValidationReport) -> None:
    """Add target-reduction suggestions based on largest target-driven spaces."""
    floor = spec.floors[floor_id]
    candidates = [
        (space.id, space.type, _target_area_cells(space, spec.grid.minor))
        for space in floor.spaces
        if _target_area_cells(space, spec.grid.minor) is not None
    ]
    candidates = [item for item in candidates if item[2] is not None]
    if not candidates:
        report.suggestions.append(f"Reduce area targets on {floor_id} or increase envelope size.")
        return
    largest = sorted(candidates, key=lambda item: item[2], reverse=True)[:2]
    for space_id, space_type, target_cells in largest:
        assert target_cells is not None
        reduce_cells = max(1, int(target_cells * 0.15))
        report.suggestions.append(
            f"Reduce {floor_id}:{space_id} ({space_type}) target by about {reduce_cells} cells "
            f"({cells_to_sqm(reduce_cells, spec.grid.minor):.1f}sqm)."
        )


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


def _rects_overlap(
    ax: int,
    ay: int,
    aw: int,
    ah: int,
    bx: int,
    by: int,
    bw: int,
    bh: int,
) -> bool:
    """Return True when two axis-aligned rectangles overlap with positive area."""
    return not (ax + aw <= bx or bx + bw <= ax or ay + ah <= by or by + bh <= ay)


def cells_to_sqm(cells: int, minor_grid: int) -> float:
    """Convert cell count to square meters."""
    return (cells * (minor_grid**2)) / 1_000_000.0
