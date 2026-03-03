"""Stage 1: Grid snap and floor metrics computation."""

from __future__ import annotations

import math
from dataclasses import dataclass

from plan_engine.constants import MAJOR_GRID_MM, TATAMI_MM2


@dataclass(frozen=True)
class FloorMetrics:
    """Metrics for a single floor derived from the snapped envelope.

    Attributes:
        envelope_w_mm: Snapped envelope width in mm.
        envelope_d_mm: Snapped envelope depth in mm.
        cols: Number of grid columns (w / 910).
        rows: Number of grid rows (d / 910).
        total_cells: Total grid cells per floor (cols x rows).
        area_jo: Floor area in tatami (total_cells x 910² / TATAMI_MM2).
    """

    envelope_w_mm: int
    envelope_d_mm: int
    cols: int
    rows: int
    total_cells: int
    area_jo: float


def _snap_to_grid(meters: float) -> int:
    """Snap a dimension in meters to the nearest 910mm multiple.

    Uses round-half-up: values at exactly half-grid (455mm) round up.

    Args:
        meters: Dimension in meters.

    Returns:
        Snapped dimension in mm.

    Raises:
        ValueError: If the result would be zero or negative.
    """
    mm = meters * 1000
    snapped = math.floor(mm / MAJOR_GRID_MM + 0.5) * MAJOR_GRID_MM
    if snapped <= 0:
        raise ValueError(
            f"envelope dimension {meters}m snaps to {snapped}mm "
            f"(must be at least {MAJOR_GRID_MM}mm)"
        )
    return snapped


def compute_metrics(envelope_w_m: float, envelope_d_m: float) -> FloorMetrics:
    """Compute floor metrics from envelope dimensions in meters.

    Snaps both dimensions to the nearest 910mm multiple, then computes
    grid cell counts and tatami area.

    Args:
        envelope_w_m: Envelope width in meters.
        envelope_d_m: Envelope depth in meters.

    Returns:
        FloorMetrics with snapped dimensions and derived values.
    """
    w_mm = _snap_to_grid(envelope_w_m)
    d_mm = _snap_to_grid(envelope_d_m)
    cols = w_mm // MAJOR_GRID_MM
    rows = d_mm // MAJOR_GRID_MM
    total_cells = cols * rows
    area_jo = (total_cells * MAJOR_GRID_MM * MAJOR_GRID_MM) / TATAMI_MM2
    return FloorMetrics(
        envelope_w_mm=w_mm,
        envelope_d_mm=d_mm,
        cols=cols,
        rows=rows,
        total_cells=total_cells,
        area_jo=area_jo,
    )
