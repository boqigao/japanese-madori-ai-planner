from __future__ import annotations

from typing import TYPE_CHECKING

from plan_engine.constants import (
    CIRCULATION_SPACE_TYPES,
    TOILET_SPACE_TYPES,
    WET_CORE_SPACE_TYPES,
    WET_MODULE_SIZES_MM,
    mm_to_cells,
)
from plan_engine.preflight.topology import _edge_ids
from plan_engine.solver.rect_var import _find_global_stair

if TYPE_CHECKING:
    from plan_engine.models import PlanSpec, ValidationReport


def _check_shower_requires_washstand(spec: PlanSpec, floor_id: str, report: ValidationReport) -> None:
    """Validate that a floor with shower also has at least one washstand."""
    floor = spec.floors[floor_id]
    has_shower = any(s.type == "shower" for s in floor.spaces)
    has_washstand = any(s.type == "washstand" for s in floor.spaces)
    if has_shower and not has_washstand:
        report.errors.append(
            f"preflight: {floor_id} has shower but no washstand (shower requires adjacent washstand)"
        )


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
        report.errors.append(f"preflight: {floor_id} defines toilet/wc but has no hall/entry/stair circulation node")
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
        report.errors.append(f"preflight: {floor_id}:{toilet_id} has no circulation topology edge to hall/entry/stair")
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
    wet_core_ids = [space_id for space_id, space_type in space_type_by_id.items() if space_type in WET_CORE_SPACE_TYPES]
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
        report.errors.append(f"preflight: {floor_id} defines wet core but has no hall/entry/stair circulation node")
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

    report.errors.append(f"preflight: {floor_id} wet core has no circulation topology edge to hall/entry/stair")
    report.suggestions.append(
        f"Add at least one topology adjacency like [<wash_or_bath>, <hall_or_entry_or_stair>, required] on {floor_id}."
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
        return any(not (rx + rw <= ox or ox + ow <= rx or ry + rh <= oy or oy + oh <= ry) for ox, oy, ow, oh in others)

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
            trial = [*placed, rect]
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
