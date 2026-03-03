"""Unit tests for Stage 1: grid snap and floor metrics."""

from __future__ import annotations

import pytest

from plan_engine.generator.metrics import FloorMetrics, _snap_to_grid, compute_metrics


class TestSnapToGrid:
    def test_exact_alignment(self):
        """8.190m = 8190mm = 9 x 910mm → 8190."""
        assert _snap_to_grid(8.190) == 8190

    def test_round_up(self):
        """8.0m = 8000mm, 8000/910 = 8.79 → rounds to 9 → 8190mm."""
        assert _snap_to_grid(8.0) == 8190

    def test_round_down(self):
        """8.5m = 8500mm → 8190 (9x910) is 310 away, 9100 (10x910) is 600 away."""
        assert _snap_to_grid(8.5) == 8190

    def test_half_grid_rounds_up(self):
        """Exactly halfway between two multiples rounds up."""
        # 910 * 5 = 4550, 910 * 6 = 5460 → midpoint = 5005mm = 5.005m
        assert _snap_to_grid(5.005) == 5460

    def test_small_value(self):
        """0.91m → 910mm (1 grid unit)."""
        assert _snap_to_grid(0.91) == 910

    def test_very_small_raises(self):
        """0.1m → would snap to 0 → error."""
        with pytest.raises(ValueError, match="must be at least"):
            _snap_to_grid(0.1)

    def test_large_value(self):
        """15.0m = 15000mm → 16x910 = 14560 or 17x910 = 15470."""
        result = _snap_to_grid(15.0)
        assert result % 910 == 0
        assert result in (14560, 15470)


class TestComputeMetrics:
    def test_8x9_envelope(self):
        """Standard 8x9m envelope."""
        m = compute_metrics(8.0, 9.0)
        assert m.envelope_w_mm % 910 == 0
        assert m.envelope_d_mm % 910 == 0
        assert m.cols == m.envelope_w_mm // 910
        assert m.rows == m.envelope_d_mm // 910
        assert m.total_cells == m.cols * m.rows
        assert m.area_jo == pytest.approx(m.total_cells * 910 * 910 / 1_620_000)

    def test_exact_grid_alignment(self):
        """9.1x6.37m — 9100mm = 10x910, 6370mm → 7x910 = 6370."""
        m = compute_metrics(9.1, 6.37)
        assert m.envelope_w_mm == 9100  # 10 x 910
        assert m.envelope_d_mm == 6370  # 7 x 910
        assert m.cols == 10
        assert m.rows == 7
        assert m.total_cells == 70

    def test_area_jo_correct(self):
        """Verify area_jo computation for known values."""
        m = compute_metrics(9.1, 9.1)
        assert m.envelope_w_mm == 9100
        assert m.envelope_d_mm == 9100
        # 10 x 10 = 100 cells, each 910x910 = 828100mm²
        # 100 x 828100 / 1620000 = 51.11...
        assert m.area_jo == pytest.approx(100 * 910 * 910 / 1_620_000)

    def test_returns_frozen(self):
        m = compute_metrics(8.0, 9.0)
        assert isinstance(m, FloorMetrics)
        with pytest.raises(AttributeError):
            m.cols = 99  # type: ignore[misc]
