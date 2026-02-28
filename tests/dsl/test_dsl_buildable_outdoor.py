from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from plan_engine.dsl import load_plan_spec


def _fixture_path(name: str) -> Path:
    return Path(__file__).resolve().parents[2] / "resources" / "specs" / name


def _write_yaml(path: Path, payload: dict) -> Path:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def test_dsl_parses_floor_buildable_mask_and_outdoor_space() -> None:
    spec = load_plan_spec(_fixture_path("buildable_balcony_valid.yaml"))

    floor = spec.floors["F1"]
    assert len(floor.buildable_mask) == 1
    assert floor.buildable_mask[0].w == 2730

    classes = {space.id: space.space_class for space in floor.spaces}
    assert classes["balcony1"] == "outdoor"
    assert classes["entry"] == "indoor"


def test_dsl_defaults_buildable_mask_to_full_envelope(tmp_path: Path) -> None:
    payload = {
        "version": "0.2",
        "units": "mm",
        "grid": {"minor": 455, "major": 910},
        "site": {
            "envelope": {"type": "rectangle", "width": 1820, "depth": 1820},
            "north": "top",
        },
        "floors": {
            "F1": {
                "spaces": [{"id": "storage1", "type": "storage"}],
                "topology": {"adjacency": []},
            }
        },
    }
    spec = load_plan_spec(_write_yaml(tmp_path / "default_buildable.yaml", payload))

    buildable = spec.floors["F1"].buildable_mask
    assert len(buildable) == 1
    assert (buildable[0].x, buildable[0].y, buildable[0].w, buildable[0].h) == (0, 0, 1820, 1820)


def test_dsl_rejects_misaligned_buildable_mask(tmp_path: Path) -> None:
    payload = {
        "version": "0.2",
        "units": "mm",
        "grid": {"minor": 455, "major": 910},
        "site": {
            "envelope": {"type": "rectangle", "width": 3640, "depth": 2730},
            "north": "top",
        },
        "floors": {
            "F1": {
                "buildable": [{"x": 100, "y": 0, "w": 1820, "h": 2730}],
                "spaces": [{"id": "storage1", "type": "storage"}],
                "topology": {"adjacency": []},
            }
        },
    }

    with pytest.raises(ValueError, match="must align to 455mm grid"):
        load_plan_spec(_write_yaml(tmp_path / "bad_buildable.yaml", payload))
