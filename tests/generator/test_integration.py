"""Integration tests: gen_spec.py → load_plan_spec → run_preflight."""

from __future__ import annotations

import tempfile
from pathlib import Path

from gen_spec import main
from plan_engine.dsl import load_plan_spec
from plan_engine.preflight.core import run_preflight


class TestGenSpecIntegration:
    def test_5ldk_8x9_passes_preflight(self):
        """Generated 5LDK 8x9 spec loads and passes preflight with 0 errors."""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            output = f.name

        result = main(["--envelope", "8x9", "--rooms", "5ldk", "--output", output])
        assert result == 0

        spec = load_plan_spec(output)
        pf = run_preflight(spec)
        assert len(pf.report.errors) == 0

        Path(output).unlink()

    def test_3ldk_9x6_passes_preflight(self):
        """Generated 3LDK 9.1x6.4 spec passes preflight."""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            output = f.name

        result = main(["--envelope", "9.1x6.4", "--rooms", "3ldk", "--output", output])
        assert result == 0

        spec = load_plan_spec(output)
        pf = run_preflight(spec)
        assert len(pf.report.errors) == 0

        Path(output).unlink()

    def test_4ldk_10x8_passes_preflight(self):
        """Generated 4LDK 10x8 spec passes preflight."""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            output = f.name

        result = main(["--envelope", "10x8", "--rooms", "4ldk", "--output", output])
        assert result == 0

        spec = load_plan_spec(output)
        pf = run_preflight(spec)
        assert len(pf.report.errors) == 0

        Path(output).unlink()

    def test_1f_3ldk_12x8_passes_preflight(self):
        """Generated 1F 3LDK 12x8 spec passes preflight."""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            output = f.name

        result = main([
            "--envelope", "12x8",
            "--rooms", "3ldk",
            "--floors", "1",
            "--output", output,
        ])
        assert result == 0

        spec = load_plan_spec(output)
        pf = run_preflight(spec)
        assert len(pf.report.errors) == 0

        Path(output).unlink()
