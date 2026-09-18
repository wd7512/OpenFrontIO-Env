"""TDD tests for the play -> retro -> memory cycle.

Scripted fixtures only: no test here launches a model. The cycle is:
play (blind, game MCP tools) -> retro (coach: reads tape + report + curated
sources, writes memory.md) -> next game reads the memory in its prompt.
"""

from __future__ import annotations

import json
from pathlib import Path

from openfront_mcp import cycle as cy


def test_memory_store_versions_and_latest(tmp_path: Path) -> None:
    store = cy.MemoryStore(tmp_path / "memories")
    assert store.latest() is None
    assert store.save("attack early") == 1
    assert store.save("attack early, observe first") == 2
    assert store.latest() == "attack early, observe first\n"
    assert (tmp_path / "memories" / "memory-v1.md").read_text() == "attack early\n"


def test_memory_store_rejects_empty(tmp_path: Path) -> None:
    import pytest

    store = cy.MemoryStore(tmp_path / "memories")
    with pytest.raises(ValueError, match="empty"):
        store.save("   ")


def test_solo_prompt_carries_memory_when_given() -> None:
    from openfront_mcp.live_smoke import build_solo_prompt

    prompt = build_solo_prompt(20, memory="LESSON: strike decisively, never drizzle.")
    assert "LESSON: strike decisively" in prompt
    plain = build_solo_prompt(20)
    assert "LESSON" not in plain


def test_build_config_without_mcp_is_coach_shaped(tmp_path: Path) -> None:
    from openfront_mcp import opencode_launcher as ol

    cfg = ol.build_config(
        model="opencode-go/muse-spark-1.3-contributor",
        mcp=None,
        agent_name="coach",
        agent_prompt="coach prompt",
        provider="opencode-go",
        key_env_var="OPENCODE_API_KEY",
        base_url=ol.PROVIDER_BASE_URLS["opencode-go"],
    )
    assert "mcp" not in cfg
    assert cfg["permission"]["*"] == "deny"
    for tool in ("read", "edit", "write"):
        assert cfg["permission"][tool] == "allow"


def test_coach_bundle_assembles_report_tape_and_sources(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "live_result.json").write_text('{"summary": {}}')
    (run_dir / "record.json").write_text('{"ticks": 100}')
    src = tmp_path / "srcfile.py"
    src.write_text("x = 1\n")
    bundle = tmp_path / "bundle"
    files = cy.assemble_coach_bundle(run_dir, [src], bundle, max_chars=10_000)
    assert "live_result.json" in files and "record.json" in files
    assert "srcfile.py" in files
    assert (bundle / "live_result.json").read_text() == '{"summary": {}}'


def test_coach_prompt_names_bundle_and_output(tmp_path: Path) -> None:
    prompt = cy.build_coach_prompt(["report.txt", "record.json"], "memory.md")
    assert "report.txt" in prompt and "memory.md" in prompt
    assert "game" not in prompt.lower().replace("endgame", "")


def test_ledger_appends_jsonl(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.jsonl"
    cy.append_ledger(
        ledger,
        {"cycle": 1, "tiles": 100, "winner": None, "model": "m"},
    )
    row = json.loads(ledger.read_text().splitlines()[0])
    assert row["cycle"] == 1 and row["tiles"] == 100


def _git_repo(path: Path) -> None:
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=str(path), check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=str(path), check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=str(path), check=True)
    (path / "tracked.txt").write_text("v1")
    (path / "cycles").mkdir()
    subprocess.run(["git", "add", "-A"], cwd=str(path), check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=str(path), check=True)


def test_check_repo_clean_ignores_baseline_only(tmp_path: Path) -> None:
    _git_repo(tmp_path)
    (tmp_path / "old-dirt.txt").write_text("pre-existing")
    baseline = cy._git_status_lines(tmp_path)
    cy.check_repo_clean(tmp_path, baseline)  # must not raise


def test_check_repo_clean_fails_on_new_cycles_touch(tmp_path: Path) -> None:
    import pytest

    _git_repo(tmp_path)
    baseline = cy._git_status_lines(tmp_path)
    # Even cycles/ is guarded: a stray coach write there could silently
    # rewrite a memory file or the ledger. The next version is saved only
    # after this check passes.
    (tmp_path / "cycles" / "memory-v9.md").write_text("coach was here")
    with pytest.raises(cy.CycleSafetyError, match="coach touched the repository"):
        cy.check_repo_clean(tmp_path, baseline)


def test_check_repo_clean_fails_on_new_src_touch(tmp_path: Path) -> None:
    import pytest

    _git_repo(tmp_path)
    baseline = cy._git_status_lines(tmp_path)
    (tmp_path / "tracked.txt").write_text("coach was here")
    with pytest.raises(cy.CycleSafetyError, match="coach touched the repository"):
        cy.check_repo_clean(tmp_path, baseline)


def test_coach_only_rejects_missing_run_dir(tmp_path: Path) -> None:
    import pytest

    with pytest.raises(ValueError, match="run dir not found"):
        cy.coach_only(
            cycles_root=tmp_path,
            run_dir=tmp_path / "nope",
            model="m",
            provider="p",
            key_env_var="K",
            base_url=None,
            api_key="k",
        )
