"""Keyless structure tests for the docs/lit-review first pass (iter_1)."""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LIT = REPO / "docs" / "lit-review"
ITER1 = LIT / "iter_1"

QUESTION_RE = re.compile(r"^\s*(\d+)\.\s+")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_readme_exists_and_points_to_batch_and_lit_watch():
    readme = LIT / "README.md"
    assert readme.is_file(), "docs/lit-review/README.md missing"
    text = _read(readme).lower()
    assert "batch" in text, "README must mention the batch"
    assert "lit-watch" in text, "README must mention lit-watch"


def test_references_bib_has_seed_entries():
    bib = LIT / "references.bib"
    assert bib.is_file(), "docs/lit-review/references.bib missing"
    text = _read(bib)
    assert text.count("@") >= 13, "references.bib must contain >=13 entries"


def test_seed_files_live_in_iter_1():
    for name in ("seed.md", "seed.bib"):
        path = ITER1 / name
        assert path.is_file(), f"iter_1/{name} missing"


def test_proposal_mentions_pmr_and_tick():
    proposal = ITER1 / "proposal.md"
    assert proposal.is_file(), "iter_1/proposal.md missing"
    text = _read(proposal)
    assert "PMR" in text, "proposal must mention PMR"
    assert "tick" in text.lower(), "proposal must mention tick"


def test_paper_note_uses_paper_title():
    notes = list(ITER1.glob("civbench-*.md"))
    assert notes, "iter_1 must contain the CivBench paper note"
    text = _read(notes[0])
    assert "A Long-Horizon Benchmark for Tool-Mediated Agents" in text


def test_questions_count_and_sections():
    questions = ITER1 / "research-questions.md"
    assert questions.is_file(), "research-questions.md missing"
    lines = _read(questions).splitlines()
    numbers = [int(m.group(1)) for line in lines if (m := QUESTION_RE.match(line))]
    assert len(numbers) == 180, f"expected 180 questions, found {len(numbers)}"
    assert numbers == list(range(1, 181)), "questions must be numbered 1..180"
    headers = [line for line in lines if line.startswith("## ")]
    assert len(headers) == 30, f"expected 30 section headers, found {len(headers)}"


def test_no_later_iterations_exist():
    for dirname in ("iter_2", "iter_3", "iter_4", "iter_5"):
        assert not (LIT / dirname).exists(), (
            f"{dirname}/ must not exist: only one research pass has happened"
        )
