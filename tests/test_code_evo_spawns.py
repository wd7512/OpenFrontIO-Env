"""Spawn registry loading and validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openfrontbench.code_evo.spawns import SpawnError, load_registry
from openfrontbench.paths import REPO_ROOT


def test_europe_registry_loads_with_four_spawns() -> None:
    registry = load_registry(REPO_ROOT / "config" / "spawns" / "europe.json")
    assert registry.map == "europe"
    assert [s.id for s in registry.spawns] == ["NW", "NE", "SW", "SE"]
    assert len(registry.sha256) == 64
    se = registry.spawns[3]
    assert (se.x, se.y) == (2118, 1308)


def test_registry_rejects_bad_payloads(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"map": "europe", "spawns": []}), encoding="utf-8")
    with pytest.raises(SpawnError):
        load_registry(bad)
    bad.write_text(json.dumps({"map": "", "spawns": [{"id": "A", "x": 1}]}))
    with pytest.raises(SpawnError):
        load_registry(bad)
    missing = tmp_path / "missing.json"
    with pytest.raises(SpawnError):
        load_registry(missing)
