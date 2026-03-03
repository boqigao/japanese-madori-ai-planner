"""Unit tests for YAML emission and feasibility check."""

from __future__ import annotations

from plan_engine.generator.cli import GeneratorArgs
from plan_engine.generator.distribute import distribute_rooms
from plan_engine.generator.emit import build_spec
from plan_engine.generator.metrics import compute_metrics


class TestBuildSpec:
    def test_output_has_required_keys(self):
        """Output dict has version, units, grid, site, floors."""
        args = GeneratorArgs(envelope_w_m=8.0, envelope_d_m=9.0, n_ldk=3)
        metrics = compute_metrics(8.0, 9.0)
        plans = distribute_rooms(args, metrics)
        spec, _report = build_spec(metrics, plans, "U_turn", "top")

        assert spec["version"] == 0.2
        assert spec["units"] == "mm"
        assert "grid" in spec
        assert spec["grid"]["minor"] == 455
        assert spec["grid"]["major"] == 910
        assert "site" in spec
        assert spec["site"]["envelope"]["width"] == metrics.envelope_w_mm
        assert spec["site"]["envelope"]["depth"] == metrics.envelope_d_mm
        assert spec["site"]["north"] == "top"
        assert "floors" in spec

    def test_2f_has_stair(self):
        """2F spec has stair configuration on F1."""
        args = GeneratorArgs(envelope_w_m=8.0, envelope_d_m=9.0, n_ldk=3)
        metrics = compute_metrics(8.0, 9.0)
        plans = distribute_rooms(args, metrics)
        spec, _ = build_spec(metrics, plans, "U_turn", "top")

        assert "F1" in spec["floors"]
        assert "core" in spec["floors"]["F1"]
        stair = spec["floors"]["F1"]["core"]["stair"]
        assert stair["type"] == "U_turn"
        assert stair["connects"] == {"F1": "hall1", "F2": "hall2"}

    def test_1f_no_stair(self):
        """1F spec has no stair."""
        args = GeneratorArgs(envelope_w_m=12.0, envelope_d_m=8.0, n_ldk=3, floors=1)
        metrics = compute_metrics(12.0, 8.0)
        plans = distribute_rooms(args, metrics)
        spec, _ = build_spec(metrics, plans, "U_turn", "top")

        assert "F1" in spec["floors"]
        assert "core" not in spec["floors"]["F1"]
        assert "F2" not in spec["floors"]

    def test_spaces_have_area(self):
        """Variable rooms have area.target_tatami set."""
        args = GeneratorArgs(envelope_w_m=9.1, envelope_d_m=6.4, n_ldk=3)
        metrics = compute_metrics(9.1, 6.4)
        plans = distribute_rooms(args, metrics)
        spec, _ = build_spec(metrics, plans, "U_turn", "top")

        for _floor_key, floor_data in spec["floors"].items():
            for space in floor_data["spaces"]:
                if space["type"] not in ("toilet", "washroom", "bath", "washstand", "shower"):
                    assert "area" in space, f"{space['id']} missing area"
                    assert space["area"]["target_tatami"] > 0

    def test_topology_present(self):
        """Each floor has topology.adjacency."""
        args = GeneratorArgs(envelope_w_m=8.0, envelope_d_m=9.0, n_ldk=5)
        metrics = compute_metrics(8.0, 9.0)
        plans = distribute_rooms(args, metrics)
        spec, _ = build_spec(metrics, plans, "U_turn", "top")

        for _floor_key, floor_data in spec["floors"].items():
            assert "topology" in floor_data
            assert "adjacency" in floor_data["topology"]
            assert len(floor_data["topology"]["adjacency"]) > 0

    def test_feasibility_no_errors(self):
        """Normal config produces no errors."""
        args = GeneratorArgs(envelope_w_m=8.0, envelope_d_m=9.0, n_ldk=3)
        metrics = compute_metrics(8.0, 9.0)
        plans = distribute_rooms(args, metrics)
        _, report = build_spec(metrics, plans, "U_turn", "top")

        assert report.ok
        assert len(report.floor_summaries) == 2

    def test_hall_has_shape(self):
        """Halls have shape: allow [L2], rect_components_max 3."""
        args = GeneratorArgs(envelope_w_m=8.0, envelope_d_m=9.0, n_ldk=3)
        metrics = compute_metrics(8.0, 9.0)
        plans = distribute_rooms(args, metrics)
        spec, _ = build_spec(metrics, plans, "U_turn", "top")

        for floor_data in spec["floors"].values():
            for space in floor_data["spaces"]:
                if space["type"] == "hall":
                    assert "shape" in space
                    assert "L2" in space["shape"]["allow"]
                    assert space["shape"]["rect_components_max"] == 3
