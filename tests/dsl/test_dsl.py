from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from plan_engine.dsl import load_plan_spec


def _write_yaml(path: Path, payload: dict) -> Path:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def _minimal_payload() -> dict:
    return {
        "version": "0.2",
        "units": "mm",
        "grid": {"minor": 455, "major": 910},
        "site": {
            "envelope": {"type": "rectangle", "width": 1820, "depth": 1820},
            "north": "top",
        },
        "floors": {
            "F1": {
                "spaces": [{"id": "entry", "type": "entry"}],
                "topology": {"adjacency": []},
            }
        },
    }


def test_load_plan_spec_success(tmp_path: Path) -> None:
    path = _write_yaml(tmp_path / "ok.yaml", _minimal_payload())
    spec = load_plan_spec(path)
    assert spec.units == "mm"
    assert spec.site.envelope.width == 1820


def test_load_plan_spec_rejects_non_mm_units(tmp_path: Path) -> None:
    payload = _minimal_payload()
    payload["units"] = "cm"
    path = _write_yaml(tmp_path / "bad_units.yaml", payload)
    with pytest.raises(ValueError, match="only mm units"):
        load_plan_spec(path)


def test_load_plan_spec_rejects_bad_grid(tmp_path: Path) -> None:
    payload = _minimal_payload()
    payload["grid"]["minor"] = 910
    path = _write_yaml(tmp_path / "bad_grid.yaml", payload)
    with pytest.raises(ValueError, match="minor grid"):
        load_plan_spec(path)


def test_load_plan_spec_rejects_non_rectangular_envelope(tmp_path: Path) -> None:
    payload = _minimal_payload()
    payload["site"]["envelope"]["type"] = "polygon"
    path = _write_yaml(tmp_path / "bad_envelope.yaml", payload)
    with pytest.raises(ValueError, match="rectangular envelopes"):
        load_plan_spec(path)


def test_load_plan_spec_rejects_misaligned_min_width(tmp_path: Path) -> None:
    payload = _minimal_payload()
    payload["floors"]["F1"]["spaces"][0]["size_constraints"] = {"min_width": 1000}
    path = _write_yaml(tmp_path / "bad_min_width.yaml", payload)
    with pytest.raises(ValueError, match="must align to minor grid"):
        load_plan_spec(path)


def test_load_plan_spec_rejects_l2_for_non_ldk_hall(tmp_path: Path) -> None:
    payload = _minimal_payload()
    payload["floors"]["F1"]["spaces"] = [
        {
            "id": "bed1",
            "type": "bedroom",
            "shape": {"allow": ["L2"], "rect_components_max": 2},
        }
    ]
    path = _write_yaml(tmp_path / "bad_l2.yaml", payload)
    with pytest.raises(ValueError, match="cannot use L2"):
        load_plan_spec(path)


def test_load_plan_spec_rejects_stair_missing_coordinate(tmp_path: Path) -> None:
    payload = _minimal_payload()
    payload["floors"]["F1"]["core"] = {
        "stair": {
            "id": "stair",
            "type": "straight",
            "width": 910,
            "floor_height": 2730,
            "riser_pref": 230,
            "tread_pref": 210,
            "connects": {"F1": "hall1"},
            "placement": {"x": 910},
        }
    }
    path = _write_yaml(tmp_path / "bad_stair_place.yaml", payload)
    with pytest.raises(ValueError, match="requires both x and y"):
        load_plan_spec(path)


def test_load_plan_spec_rejects_bad_topology_pairs(tmp_path: Path) -> None:
    payload = _minimal_payload()
    payload["floors"]["F1"]["topology"] = {"adjacency": [["entry"]]}
    path = _write_yaml(tmp_path / "bad_topology.yaml", payload)
    with pytest.raises(ValueError, match="2-item or 3-item lists"):
        load_plan_spec(path)
