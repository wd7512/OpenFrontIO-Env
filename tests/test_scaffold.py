from __future__ import annotations

from pathlib import Path

import pytest

from openfront_mcp import core_queries
from openfront_mcp.__main__ import main
from openfront_mcp.diary import append_diary, read_diary
from openfront_mcp.metrics import pmr, rag_at_k
from openfront_mcp.narrate import narrate_overview
from openfront_mcp.server import TOOLS, get_pin, list_scenarios


def test_pin_names_version() -> None:
    assert "v0.33.14" in get_pin()


def test_tool_registry_lists_both_scenarios() -> None:
    assert set(TOOLS) == {"get_pin", "list_scenarios"}
    out = list_scenarios()
    assert "box-small-2nations" in out
    assert "box-small-4nations-mixed" in out


def test_narrate_minimal_obs() -> None:
    assert narrate_overview({"tick": 50, "scenario": "box-small-2nations"})
    assert "50" in narrate_overview({"tick": 50, "scenario": "box-small-2nations"})


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
