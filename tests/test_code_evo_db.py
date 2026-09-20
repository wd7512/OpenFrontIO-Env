"""Program DB append/load/best/diverse and candidate validation."""

from __future__ import annotations

from pathlib import Path

from openfrontbench.code_evo import program_db
from openfrontbench.code_evo.evolve import CandidateError, validate_candidate
from openfrontbench.paths import REPO_ROOT

BASELINE = REPO_ROOT / "src" / "openfrontbench" / "policies" / "evolve_me.py"


def _entry(entry_id: str, sha: str, score: float) -> dict[str, object]:
    return {
        "id": entry_id,
        "parent_id": None,
        "policy_sha256": sha,
        "mean_score": score,
        "spawns": [],
        "source": "src",
    }


def test_db_roundtrip_and_selection(tmp_path: Path) -> None:
    db = tmp_path / "db.jsonl"
    assert program_db.load_entries(db) == []
    assert program_db.best_entry([]) is None
    program_db.append_entry(db, _entry("a", "sha-a", 10.0))
    program_db.append_entry(db, _entry("b", "sha-b", 30.0))
    program_db.append_entry(db, _entry("c", "sha-c", 20.0))
    entries = program_db.load_entries(db)
    assert len(entries) == 3
    best = program_db.best_entry(entries)
    assert best is not None and best["id"] == "b"
    diverse = program_db.diverse_entry(entries, "sha-b", seed=0)
    assert diverse is not None and diverse["id"] in ("a", "c")
    assert program_db.diverse_entry(entries, "sha-x", seed=0) is not None
    single = [_entry("only", "sha-o", 5.0)]
    assert program_db.diverse_entry(single, "sha-o") is None


def test_validate_candidate_accepts_baseline() -> None:
    text = validate_candidate(BASELINE)
    assert "class EvolvingPolicy" in text


def test_validate_candidate_rejects_bad_edits(tmp_path: Path) -> None:
    import pytest

    baseline = BASELINE.read_text(encoding="utf-8")
    no_markers = tmp_path / "no_markers.py"
    no_markers.write_text("class EvolvingPolicy:\n    pass\n", encoding="utf-8")
    with pytest.raises(CandidateError):
        validate_candidate(no_markers)
    bad_import = tmp_path / "bad_import.py"
    bad_import.write_text(
        baseline.replace("from typing import Any", "import os\nfrom typing import Any"),
        encoding="utf-8",
    )
    with pytest.raises(CandidateError):
        validate_candidate(bad_import)
