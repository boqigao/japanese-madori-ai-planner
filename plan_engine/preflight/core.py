from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from plan_engine.constants import (
    MAJOR_ROOM_TYPES,
    WET_MODULE_SIZES_MM,
    is_indoor_space_type,
    mm_to_cells,
)
from plan_engine.models import BedroomReachabilityViolation, ValidationReport
from plan_engine.preflight.closets import (
    _check_closet_semantics,
    _check_reference_consistency,
    _warn_bedrooms_without_closet,
    _warn_closet_wall_feasibility,
)
from plan_engine.preflight.topology import _check_topology_reachability, _hall_fanout
from plan_engine.preflight.wet import (
    _check_shower_requires_washstand,
    _check_toilet_circulation_topology,
    _check_wet_cluster_fit,
    _check_wet_core_circulation_topology,
    _rects_overlap,
)
from plan_engine.solver.rect_var import _compute_stair_footprint, _find_global_stair
from plan_engine.solver.space_specs import (
    _embedded_closet_max_area_cells,
    _embedded_closet_min_area_cells,
    _max_area_cells,
    _min_area_cells,
    _target_area_cells,
)

if TYPE_CHECKING:
    from plan_engine.models import PlanSpec


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
        _check_major_room_exterior_touch_feasibility(
            spec=spec,
            floor_id=floor_id,
            envelope_w_cells=envelope_w,
            envelope_h_cells=envelope_h,
            report=report,
        )
        _check_closet_semantics(spec, floor_id, report)
        _warn_bedrooms_without_closet(spec, floor_id, report)
        _warn_closet_wall_feasibility(spec, floor_id, report)
        _check_shower_requires_washstand(spec, floor_id, report)
        _check_toilet_circulation_topology(spec, floor_id, report)
        _check_wet_core_circulation_topology(spec, floor_id, report)
        _check_wet_cluster_fit(spec, floor_id, envelope_w, envelope_h, report)

        if hall_fanout >= 8:
            report.warnings.append(
                f"preflight: {floor_id} hall adjacency fanout is {hall_fanout} (>=8), this often makes solving harder"
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
            report.suggestions.append(f"Reduce {floor_id} hall adjacency fanout from {stats.hall_fanout} to <=6.")
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
    return dict.fromkeys(floors_with_stair, stair_area)


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
    for closet in floor.embedded_closets:
        min_cells += _embedded_closet_min_area_cells(closet, spec.grid.minor)
        max_cells += _embedded_closet_max_area_cells(closet, spec.grid.minor)
    return min_cells, max_cells


def _check_envelope_alignment(spec: PlanSpec, report: ValidationReport) -> None:
    """Verify site envelope aligns to the minor grid (defensive duplicate check)."""
    if spec.site.envelope.width % spec.grid.minor != 0 or spec.site.envelope.depth % spec.grid.minor != 0:
        report.errors.append(f"preflight: envelope width/depth must align to minor grid ({spec.grid.minor}mm)")


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


def _check_major_room_exterior_touch_feasibility(
    spec: PlanSpec,
    floor_id: str,
    envelope_w_cells: int,
    envelope_h_cells: int,
    report: ValidationReport,
) -> None:
    """Validate buildable mask can support exterior-touch major rooms.

    Args:
        spec: Parsed plan specification.
        floor_id: Floor identifier to validate.
        envelope_w_cells: Envelope width in minor-grid cells.
        envelope_h_cells: Envelope depth in minor-grid cells.
        report: Mutable report receiving preflight errors and suggestions.

    Returns:
        None.
    """
    floor = spec.floors[floor_id]
    major_space_ids = [space.id for space in floor.spaces if space.type in MAJOR_ROOM_TYPES]
    if not major_space_ids:
        return

    mask_rects = floor.buildable_mask
    # Empty mask means full-envelope buildable, which always has exterior contact.
    if not mask_rects:
        return

    has_exterior_contact = any(
        _rect_touches_envelope_edge(
            x_cells=mm_to_cells(rect.x, spec.grid.minor),
            y_cells=mm_to_cells(rect.y, spec.grid.minor),
            w_cells=mm_to_cells(rect.w, spec.grid.minor),
            h_cells=mm_to_cells(rect.h, spec.grid.minor),
            envelope_w_cells=envelope_w_cells,
            envelope_h_cells=envelope_h_cells,
        )
        for rect in mask_rects
    )
    if has_exterior_contact:
        return

    major_list = ", ".join(sorted(major_space_ids))
    report.errors.append(
        f"preflight: {floor_id} major-room exterior-touch is impossible because buildable mask has no exterior contact "
        f"(rooms: {major_list})"
    )
    report.suggestions.append(
        f"Adjust {floor_id} buildable_mask so at least one rectangle reaches envelope edge for "
        "bedroom/master_bedroom/ldk exterior-touch."
    )
    report.suggestions.append(f"Or move one of [{major_list}] to another floor where buildable mask contacts exterior.")


def _rect_touches_envelope_edge(
    x_cells: int,
    y_cells: int,
    w_cells: int,
    h_cells: int,
    envelope_w_cells: int,
    envelope_h_cells: int,
) -> bool:
    """Return True when a rectangle shares positive-length edge with envelope.

    Args:
        x_cells: Rectangle origin X in cells.
        y_cells: Rectangle origin Y in cells.
        w_cells: Rectangle width in cells.
        h_cells: Rectangle height in cells.
        envelope_w_cells: Envelope width in cells.
        envelope_h_cells: Envelope depth in cells.

    Returns:
        True when rectangle touches left/right/top/bottom boundary with
        non-zero overlap length.
    """
    if w_cells <= 0 or h_cells <= 0:
        return False
    return (
        x_cells == 0 or y_cells == 0 or x_cells + w_cells == envelope_w_cells or y_cells + h_cells == envelope_h_cells
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
                f"preflight: {floor_id} buildable rect #{index} is outside envelope ({envelope_w_mm}x{envelope_h_mm}mm)"
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


def cells_to_sqm(cells: int, minor_grid: int) -> float:
    """Convert cell count to square meters."""
    return (cells * (minor_grid**2)) / 1_000_000.0
