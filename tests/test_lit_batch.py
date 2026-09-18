"""Keyless unit tests for the lit-review batch runner (dry-run only)."""

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUN_PY = REPO / "docs" / "lit-review" / "iter_1" / "batch" / "scripts" / "run.py"
QUESTIONS = REPO / "docs" / "lit-review" / "iter_1" / "research-questions.md"
PROPOSAL = REPO / "docs" / "lit-review" / "iter_1" / "proposal.md"


def _load():
    spec = importlib.util.spec_from_file_location("lit_batch_run", RUN_PY)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_extract_questions_parses_in_sequence():
    run = _load()
    parsed = run.extract_questions(QUESTIONS)
    assert len(parsed) > 0
    assert [n for n, _ in parsed] == sorted(n for n, _ in parsed)
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
    prompt = run.prompt_for(1, "What taxonomies exist?", proposal[:200])
    assert "What taxonomies exist?" in prompt
    assert proposal[:100] in prompt


def test_dry_run_writes_stub_then_skips(tmp_path):
    run = _load()
    first = run.process_question(1, "What taxonomies exist?", "P", tmp_path)
    assert first["status"] == "dry-run"
    stub = Path(first["file"]).read_text(encoding="utf-8")
    assert "DRY-RUN" in stub
    assert "Question" in stub
    second = run.process_question(1, "What taxonomies exist?", "P", tmp_path)
    assert second["status"] == "skip"
    assert second["file"] == first["file"]


def test_live_is_refused():
    run = _load()
    assert run.main(["--live"]) == 1
    assert run.main(["--no-dry-run"]) == 1


def test_defaults_resolve_to_existing_files():
    run = _load()
    questions, proposal, reports = run._defaults()
    assert Path(questions).is_file()
    assert Path(proposal).is_file()
    assert str(reports).endswith("reports")
