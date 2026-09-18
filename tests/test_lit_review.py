"""Keyless structure tests for the docs/lit-review scaffold (T5)."""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LIT = REPO / "docs" / "lit-review"
ITER3 = LIT / "iter_3"
PROMPTS = ITER3 / "research-prompts"

QUESTION_RE = re.compile(r"^\s*(\d+)\.\s+")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_readme_exists_and_points_to_batch_and_lit_watch():
    readme = LIT / "README.md"
    assert readme.is_file(), "docs/lit-review/README.md missing"
    text = _read(readme).lower()
    assert "batch" in text, "README must mention the T6 batch"
    assert "lit-watch" in text, "README must mention lit-watch"


def test_references_bib_has_seed_entries():
    bib = LIT / "references.bib"
    assert bib.is_file(), "docs/lit-review/references.bib missing"
    text = _read(bib)
    assert text.count("@") >= 13, "references.bib must contain >=13 entries"


def test_proposal_v1_mentions_pmr_and_tick():
    proposal = LIT / "iter_1" / "proposal_v1.md"
    assert proposal.is_file(), "iter_1/proposal_v1.md missing"
    text = _read(proposal)
    assert "PMR" in text, "proposal_v1 must mention PMR"
    assert "tick" in text.lower(), "proposal_v1 must mention tick"


def test_detailed_questions_count_and_sections():
    detailed = ITER3 / "detailed_research_questions.md"
    assert detailed.is_file(), "detailed_research_questions.md missing"
    lines = _read(detailed).splitlines()
    numbers = [int(m.group(1)) for line in lines if (m := QUESTION_RE.match(line))]
    assert len(numbers) == 180, f"expected 180 questions, found {len(numbers)}"
    assert numbers == list(range(1, 181)), "questions must be numbered 1..180"
    headers = [line for line in lines if line.startswith("## ")]
    assert len(headers) == 30, f"expected 30 section headers, found {len(headers)}"


def test_grouped_questions_mentions_ten_themes():
    grouped = ITER3 / "grouped_research_questions.md"
    assert grouped.is_file(), "grouped_research_questions.md missing"
    text = _read(grouped)
    for theme in range(1, 11):
        assert f"Theme {theme}" in text, f"grouped file must mention Theme {theme}"


def test_ten_theme_prompts_exist_and_nonempty():
    for theme in range(1, 11):
        prompt = PROMPTS / f"theme-{theme}.md"
        assert prompt.is_file(), f"research-prompts/theme-{theme}.md missing"
        assert prompt.stat().st_size > 0, f"theme-{theme}.md must be non-empty"
