"""Direct tests for the shared atomic-write primitives (no daemon, no MCP)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openfrontbench.atomic import (
    OutputExistsError,
    ensure_fresh_dir,
    write_json_atomic,
    write_text_atomic,
)


def test_ensure_fresh_dir_creates_parents_and_refuses_existing(
    tmp_path: Path,
) -> None:
    out = ensure_fresh_dir(tmp_path / "a" / "b")
    assert out.is_dir()
    with pytest.raises(OutputExistsError, match="refusing to overwrite"):
        ensure_fresh_dir(tmp_path / "a" / "b")


def test_write_leaves_no_tmp_and_round_trips_sorted_json(tmp_path: Path) -> None:
    target = tmp_path / "summary.json"
    out = write_json_atomic(target, {"b": 1, "a": 2})
    assert out == target
    raw = target.read_text(encoding="utf-8")
    assert raw.endswith("\n")
    assert raw.index('"a"') < raw.index('"b"')
    assert json.loads(raw) == {"a": 2, "b": 1}
    assert list(tmp_path.glob(".*.tmp")) == []
    text_out = write_text_atomic(tmp_path / "note.txt", "hi\n")
    assert text_out.read_text(encoding="utf-8") == "hi\n"
    assert list(tmp_path.glob(".*.tmp")) == []


def test_output_exists_caught_as_file_error_and_value_error(
    tmp_path: Path,
) -> None:
    with pytest.raises((FileExistsError, ValueError)):
        ensure_fresh_dir(tmp_path)
    assert issubclass(OutputExistsError, FileExistsError)
    assert issubclass(OutputExistsError, ValueError)
