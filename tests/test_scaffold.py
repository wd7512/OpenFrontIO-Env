from __future__ import annotations

from pathlib import Path

import pytest

from openfrontbench import core_queries
from openfrontbench.__main__ import main
from openfrontbench.diary import append_diary, read_diary
from openfrontbench.metrics import pmr, rag_at_k
from openfrontbench.narrate import narrate_overview
from openfrontbench.server import TOOLS, get_pin


def test_pin_names_version() -> None:
    assert "v0.33.14" in get_pin()


def test_tool_registry_lists_pin_only() -> None:
    assert set(TOOLS) == {"get_pin"}


def test_narrate_minimal_obs() -> None:
    assert narrate_overview({"tick": 50, "scenario": "plains-human-smoke"})
    assert "50" in narrate_overview({"tick": 50, "scenario": "plains-human-smoke"})


def test_pmr() -> None:
    assert pmr(2, 100) == pytest.approx(0.02)
    assert pmr(0, 0) == 0.0


def test_rag() -> None:
    assert rag_at_k(4, 2, 10) == pytest.approx(0.5)
    assert rag_at_k(0, 0, 0) == 0.0


def test_diary_roundtrip(tmp_path: Path) -> None:
    diary = tmp_path / "diary.jsonl"
    assert read_diary(diary) == []
    append_diary(diary, {"tactical": "expanded north", "tick": 50})
    entries = read_diary(diary)
    assert len(entries) == 1
    assert entries[0]["tactical"] == "expanded north"


def test_core_queries_stubbed() -> None:
    with pytest.raises(NotImplementedError):
        core_queries.overview({})
    with pytest.raises(NotImplementedError):
        core_queries.territory({})


def test_main_callable() -> None:
    assert callable(main)
