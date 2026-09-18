"""Keyless unit tests for the T6 lit-review batch runner (dry-run only)."""

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUN_PY = (
    REPO
    / "docs"
    / "lit-review"
    / "iter_3"
    / "detailed_research_auto"
    / "scripts"
    / "run.py"
)
QUESTIONS = REPO / "docs" / "lit-review" / "iter_3" / "detailed_research_questions.md"
PROPOSAL = REPO / "docs" / "lit-review" / "iter_1" / "proposal_v1.md"

GOOD = """### Question
Q01: What taxonomies exist?

### Key Findings
- A key finding with evidence (https://doi.org/10.1234/taxonomy).

### Papers
1. **Taxonomies** — Doe et al. (2024). https://doi.org/10.1234/taxonomy
2. **More** — Roe (2023). https://arxiv.org/abs/2301.00001

### Gaps
A paper gap.

### Relevance
Relevant.
"""


def _load():
    spec = importlib.util.spec_from_file_location("lit_batch_run", RUN_PY)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_extract_questions_parses_180_in_sequence():
    run = _load()
    parsed = run.extract_questions(QUESTIONS)
    assert len(parsed) == 180
    assert [n for n, _ in parsed] == list(range(1, 181))
    assert all(text for _, text in parsed)


def test_slug_stable_and_bounded():
    run = _load()
    text = "What Taxonomies of Agent-Harness Engineering Components Exist?"
    first, second = run.slug(text), run.slug(text)
    assert first == second and first == first.lower()
    assert " " not in first and len(first.split("-")) <= 8


def test_prompt_for_contains_proposal_snippet_and_question():
    run = _load()
    proposal = PROPOSAL.read_text(encoding="utf-8")
    prompt = run.prompt_for(1, "What taxonomies exist?", proposal[:200], "brief")
    assert "What taxonomies exist?" in prompt
    assert proposal[:100] in prompt
    assert "500" in prompt and "DOI" in prompt


def test_filter_output_strips_preamble():
    run = _load()
    raw = "> thinking\n⚙ running\nHere is the report\n### Question\nBody here"
    filtered = run.filter_output(raw)
    assert filtered.startswith("### Question")
    assert ">" not in filtered.splitlines()[0]


def test_validate_accepts_good_and_rejects_bad():
    run = _load()
    ok, _ = run.validate(GOOD)
    assert ok is True
    bad_ok, reason = run.validate("hello world, nothing to see")
    assert bad_ok is False and reason


def test_dry_run_writes_stub_then_skips(tmp_path):
    run = _load()
    first = run.process_question(1, "What taxonomies exist?", "P", "B", tmp_path)
    assert first["status"] == "dry-run"
    stub = Path(first["file"]).read_text(encoding="utf-8")
    assert "DRY-RUN" in stub
    for header in ("Question", "Key Findings", "Papers", "Gaps", "Relevance"):
        assert header in stub
    second = run.process_question(1, "What taxonomies exist?", "P", "B", tmp_path)
    assert second["status"] == "skip"
    assert second["file"] == first["file"]
