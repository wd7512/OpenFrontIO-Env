"""TDD tests for the play -> retro -> memory cycle.

Scripted fixtures only: no test here launches a model. The cycle is:
play (blind, game MCP tools) -> retro (coach: reads tape + report + curated
sources, writes memory.md) -> next game reads the memory in its prompt.
"""

from __future__ import annotations

import json
from pathlib import Path

from openfrontbench import cycle as cy


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


def test_memory_store_read_pins_version(tmp_path: Path) -> None:
    import pytest

    store = cy.MemoryStore(tmp_path / "memories")
    store.save("one")
    store.save("two")
    assert store.read(1) == "one\n"
    assert store.latest_version() == 2
    with pytest.raises(ValueError, match="not found"):
        store.read(9)


def test_run_cycle_pins_memory_version_and_records_metrics(tmp_path: Path) -> None:
    root = tmp_path / "cycles"
    memories = root / "memories"
    memories.mkdir(parents=True)
    (memories / "memory-v21.md").write_text("old\n")
    (memories / "memory-v22.md").write_text("pinned playbook\n")
    (memories / "memory-v23.md").write_text("latest\n")
    seen: dict = {}

    def play_fn(**kwargs):
        seen.update(kwargs)
        return {
            "summary": {
                "decisions": [1, 2],
                "winner": None,
                "final_human": {"tiles": 42, "troops": 7},
                "metrics": {
                    "attacks": 3,
                    "attacks_after_50": 1,
                    "nation_attacks": 2,
                    "cities": 4,
                    "defense_posts": 5,
                    "tiles_peak": 99,
                    "gold_end": "123",
                },
            }
        }

    row = cy.run_cycle(
        cycles_root=root,
        play_fn=play_fn,
        play_kwargs={"output": tmp_path / "never-created"},
        model="m",
        provider="p",
        key_env_var="K",
        base_url=None,
        api_key="k",
        memory_version=22,
        min_decisions=2,
    )
    assert seen["memory"] == "pinned playbook\n"
    assert row["memory_used"] == 22
    assert row["memory_version"] is None  # no output dir, no coach
    assert row["cycle"] == 23
    assert row["valid"] is True
    assert row["play_attempts"] == 1
    assert row["attacks_after_50"] == 1
    assert row["cities"] == 4
    assert row["tiles_peak"] == 99
    assert row["gold_end"] == "123"


def _ok_play(**kwargs):
    return {
        "returncode": 0,
        "timed_out": False,
        "api_error": None,
        "summary": {"decisions": list(range(1, 21)), "winner": None},
    }


def test_invalid_run_is_not_coached_and_retried(tmp_path: Path) -> None:
    root = tmp_path / "cycles"
    (root / "memories").mkdir(parents=True)
    calls: list[dict] = []

    def flaky_play(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return {
                "returncode": 1,
                "timed_out": False,
                "api_error": "APIError: Cannot connect to API",
                "summary": {"decisions": [1, 2, 3], "winner": None},
            }
        return _ok_play(**kwargs)

    row = cy.run_cycle(
        cycles_root=root,
        play_fn=flaky_play,
        play_kwargs={"output": tmp_path / "run-1"},
        model="m",
        provider="p",
        key_env_var="K",
        base_url=None,
        api_key="k",
    )
    assert len(calls) == 2
    assert row["valid"] is True
    assert row["play_attempts"] == 2
    assert row["api_error"] is None
    # The retry writes to its own directory so the crashed attempt's
    # artifacts survive for diagnosis.
    assert calls[1]["output"] == f"{tmp_path / 'run-1'}-retry1"


def test_crashed_run_recorded_invalid_without_coach(tmp_path: Path) -> None:
    root = tmp_path / "cycles"
    (root / "memories").mkdir(parents=True)
    calls: list[dict] = []

    def crashed_play(**kwargs):
        calls.append(kwargs)
        return {
            "returncode": 1,
            "timed_out": False,
            "api_error": "APIError: Cannot connect to API",
            "summary": {"decisions": [1, 2], "winner": None},
        }

    row = cy.run_cycle(
        cycles_root=root,
        play_fn=crashed_play,
        play_kwargs={"output": tmp_path / "run-2"},
        model="m",
        provider="p",
        key_env_var="K",
        base_url=None,
        api_key="k",
        play_retries=1,
    )
    assert len(calls) == 2  # initial + one retry
    assert row["valid"] is False
    assert row["memory_version"] is None
    assert "APIError" in row["api_error"]
    # The ledger keeps the row: invalid runs are data, not dropped work.
    ledger = [
        json.loads(line) for line in (root / "ledger.jsonl").read_text().splitlines()
    ]
    assert ledger[-1]["valid"] is False


def test_short_clean_run_not_retried(tmp_path: Path) -> None:
    root = tmp_path / "cycles"
    (root / "memories").mkdir(parents=True)
    calls: list[dict] = []

    def short_play(**kwargs):
        calls.append(kwargs)
        return {
            "returncode": 0,
            "timed_out": False,
            "api_error": None,
            "summary": {"decisions": [1, 2], "winner": None},
        }

    row = cy.run_cycle(
        cycles_root=root,
        play_fn=short_play,
        play_kwargs={"output": tmp_path / "run-3"},
        model="m",
        provider="p",
        key_env_var="K",
        base_url=None,
        api_key="k",
        min_decisions=10,
    )
    assert len(calls) == 1  # a clean short run is deterministic, not flaky
    assert row["valid"] is False


def test_winner_is_valid_at_any_length(tmp_path: Path) -> None:
    assert cy.is_valid_run(
        {"returncode": 0, "summary": {"decisions": [1], "winner": "Agent"}}
    )


def test_coach_failure_is_non_fatal(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "cycles"
    (root / "memories").mkdir(parents=True)
    out = tmp_path / "run-4"
    out.mkdir()

    def boom(**_kwargs):
        raise ValueError("coach did not write memory.md")

    monkeypatch.setattr(cy, "coach_only", boom)
    row = cy.run_cycle(
        cycles_root=root,
        play_fn=_ok_play,
        play_kwargs={"output": out},
        model="m",
        provider="p",
        key_env_var="K",
        base_url=None,
        api_key="k",
    )
    assert row["memory_version"] is None
    assert "memory.md" in row["coach_error"]


def test_solo_prompt_carries_memory_when_given() -> None:
    from openfrontbench.live_smoke import build_solo_prompt

    prompt = build_solo_prompt(20, memory="LESSON: strike decisively, never drizzle.")
    assert "LESSON: strike decisively" in prompt
    plain = build_solo_prompt(20)
    assert "LESSON" not in plain


def test_build_config_without_mcp_is_coach_shaped(tmp_path: Path) -> None:
    from openfrontbench import opencode_launcher as ol

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


def test_coach_prompt_asks_for_ethos_from_engine_sources(tmp_path: Path) -> None:
    prompt = cy.build_coach_prompt(["record.json", "Config.ts"], "memory.md")
    assert "record.json" in prompt and "memory.md" in prompt
    assert "ethos" in prompt
    assert "attackLogic" in prompt and "TransportShip" in prompt
    # Timing and explicit sizing are mandatory sections, not optional colour.
    assert "When to act" in prompt and "Attack sizing" in prompt
    assert "incoming_troops" in prompt and "incoming attacks" in prompt
    # No playbook bundled: nothing tells the coach to evolve one.
    assert "previous_playbook.md" not in prompt

    evolved = cy.build_coach_prompt(
        ["record.json", "previous_playbook.md"], "memory.md", has_previous=True
    )
    assert "previous_playbook.md" in evolved


def test_cap_escalates_after_five_ceiling_finishes() -> None:
    assert cy.cap_after_cap_hits(0, 200) == (200, 0)
    assert cy.cap_after_cap_hits(4, 200) == (200, 4)
    assert cy.cap_after_cap_hits(5, 200) == (300, 0)
    assert cy.cap_after_cap_hits(5, 300) == (400, 0)


def test_coach_bundle_shares_budget_by_source_size(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    small = tmp_path / "small.py"
    small.write_text("tiny\n")
    big = tmp_path / "big.py"
    big.write_text("x" * 50_000)
    bundle = tmp_path / "bundle"
    files = cy.assemble_coach_bundle(run_dir, [small, big], bundle, max_chars=10_000)
    assert files == ["small.py", "big.py"]
    # The short source is whole; the long one takes the rest of the budget.
    assert (bundle / "small.py").read_text() == "tiny\n"
    assert len((bundle / "big.py").read_text()) < 50_000


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
