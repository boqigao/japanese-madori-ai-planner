from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from plan_engine.dsl import load_plan_spec


def _write_yaml(path: Path, payload: dict) -> Path:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def _base_payload() -> dict:
    return {
        "version": "0.2",
        "units": "mm",
        "grid": {"minor": 455, "major": 910},
        "site": {
            "envelope": {"type": "rectangle", "width": 5460, "depth": 3640},
            "north": "top",
        },
        "floors": {
            "F1": {
                "spaces": [
                    {"id": "entry", "type": "entry"},
                    {"id": "hall1", "type": "hall"},
                    {"id": "master", "type": "master_bedroom"},
                ],
                "topology": {"adjacency": [["entry", "hall1"], ["hall1", "master"]]},
            }
        },
    }


def test_parse_embedded_closet_and_wic_declarations(tmp_path: Path) -> None:
    payload = _base_payload()
    payload["floors"]["F1"]["spaces"][2]["closet"] = {
        "id": "master_closet",
        "area": {"target_tatami": 1.0},
    }
    payload["floors"]["F1"]["spaces"][2]["closets"] = [
        {
            "id": "master_wic",
            "type": "wic",
            "size_constraints": {"min_width": 910},
            "area": {"target_tatami": 2.0},
        }
    ]

    spec = load_plan_spec(_write_yaml(tmp_path / "embedded.yaml", payload))
    floor = spec.floors["F1"]
    floor_spaces = {space.id: space for space in floor.spaces}
    embedded = {closet.id: closet for closet in floor.embedded_closets}

    assert "master_closet" in embedded
    assert embedded["master_closet"].parent_id == "master"
    assert floor_spaces["master_wic"].type == "wic"
    assert floor_spaces["master_wic"].parent_id == "master"


def test_rejects_embedded_closet_non_mapping(tmp_path: Path) -> None:
    payload = _base_payload()
    payload["floors"]["F1"]["spaces"][2]["closet"] = "invalid"

    with pytest.raises(ValueError, match="embedded closet"):
        load_plan_spec(_write_yaml(tmp_path / "bad_embedded.yaml", payload))


def test_rejects_wic_missing_parent_id(tmp_path: Path) -> None:
    payload = _base_payload()
    payload["floors"]["F1"]["spaces"].append(
        {
            "id": "wic1",
            "type": "wic",
            "size_constraints": {"min_width": 910},
            "area": {"target_tatami": 2.0},
        }
    )

    with pytest.raises(ValueError, match="requires parent_id"):
        load_plan_spec(_write_yaml(tmp_path / "wic_missing_parent.yaml", payload))


def test_rejects_unknown_parent_id_for_closet(tmp_path: Path) -> None:
    payload = _base_payload()
    payload["floors"]["F1"]["spaces"].append(
        {
            "id": "closet1",
            "type": "closet",
            "parent_id": "missing_room",
            "size_constraints": {"min_width": 910},
            "area": {"target_tatami": 1.0},
        }
    )

    with pytest.raises(ValueError, match="unknown parent_id"):
        load_plan_spec(_write_yaml(tmp_path / "unknown_parent.yaml", payload))


def test_rejects_misaligned_closet_min_width(tmp_path: Path) -> None:
    payload = _base_payload()
    payload["floors"]["F1"]["spaces"].append(
        {
            "id": "closet1",
            "type": "closet",
            "parent_id": "master",
            "size_constraints": {"min_width": 1000},
            "area": {"target_tatami": 1.0},
        }
    )

    with pytest.raises(ValueError, match="must align to minor grid"):
        load_plan_spec(_write_yaml(tmp_path / "bad_closet_grid.yaml", payload))
