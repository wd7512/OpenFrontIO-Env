"""Research ledger: verdict parsing and two-file round enforcement."""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from openfrontbench.code_evo import research
from openfrontbench.code_evo.evolve import launch_research_round
from openfrontbench.paths import REPO_ROOT

BASELINE = (
    REPO_ROOT / "src" / "openfrontbench" / "policies" / "evolve_me.py"
).read_text(encoding="utf-8")


def test_parse_verdict_ship_and_hold() -> None:
    ship = research.parse_verdict(
        "notes\n## Verdict\nVERDICT: SHIP\nREASON: faster expand\n"
    )
    assert ship.ship is True
    assert ship.reason == "faster expand"
    hold = research.parse_verdict(
        "notes\n## Verdict\nVERDICT: HOLD\nREASON: needs more thought\n"
    )
    assert hold.ship is False
    assert hold.reason == "needs more thought"


def test_parse_verdict_missing_defaults_hold() -> None:
    verdict = research.parse_verdict("some notes without a trailer")
    assert verdict.ship is False


def test_parse_verdict_last_wins() -> None:
    text = "VERDICT: SHIP\nREASON: first\nVERDICT: HOLD\nREASON: changed mind\n"
    verdict = research.parse_verdict(text)
    assert verdict.ship is False
    assert verdict.reason == "changed mind"


def _work_dir(tmp_path: Path, log_text: str) -> tuple[Path, dict[str, str]]:
    work = tmp_path / "work"
    work.mkdir()
    (work / research.POLICY_FILENAME).write_text("policy v1\n", encoding="utf-8")
    (work / research.LOG_FILENAME).write_text(log_text, encoding="utf-8")
    return work, research.snapshot_files(work)


def test_two_file_rule_accepts_policy_and_log_appendix(tmp_path: Path) -> None:
    work, before = _work_dir(tmp_path, "header\n")
    (work / research.POLICY_FILENAME).write_text("policy v2\n", encoding="utf-8")
    with (work / research.LOG_FILENAME).open("a", encoding="utf-8") as stream:
        stream.write("agent notes\nVERDICT: SHIP\nREASON: x\n")
    appendix = research.check_two_file_rule(work, before, "header\n")
    assert "VERDICT: SHIP" in appendix


def test_two_file_rule_rejects_third_file(tmp_path: Path) -> None:
    work, before = _work_dir(tmp_path, "header\n")
    (work / "notes.txt").write_text("scratch\n", encoding="utf-8")
    with pytest.raises(research.RoundError, match="notes.txt"):
        research.check_two_file_rule(work, before, "header\n")


def test_two_file_rule_rejects_rewritten_history(tmp_path: Path) -> None:
    work, before = _work_dir(tmp_path, "header\n")
    (work / research.LOG_FILENAME).write_text("rewritten!\n", encoding="utf-8")
    with pytest.raises(research.RoundError, match="append-only"):
        research.check_two_file_rule(work, before, "header\n")


def test_two_file_rule_rejects_missing_log(tmp_path: Path) -> None:
    work, before = _work_dir(tmp_path, "header\n")
    (work / research.LOG_FILENAME).unlink()
    with pytest.raises(research.RoundError, match="missing"):
        research.check_two_file_rule(work, before, "header\n")


def test_repo_untouched_passes_when_idle(tmp_path: Path) -> None:
    from openfrontbench.paths import REPO_ROOT

    before = research.git_status_snapshot(REPO_ROOT)
    research.check_repo_untouched(REPO_ROOT, before)


def test_header_for_iteration_marks_forced_eval() -> None:
    header = research.header_for_iteration(3, "iter_2", 100.0, "n/a", 100.0, True)
    assert "Iteration 3" in header
    assert "forced eval" in header
    plain = research.header_for_iteration(1, "iter_0", 50.0, "n/a", 50.0, False)
    assert "forced eval" not in plain


def _stub_agent(tmp_path: Path, body: str) -> Path:
    """A fake opencode binary: runs *body* python in its cwd, exits 0."""
    stub = tmp_path / "stub_agent.py"
    stub.write_text(
        "#!/usr/bin/env python3\nimport sys\n" + body + "\n", encoding="utf-8"
    )
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return stub


def _round_kwargs(stub: Path) -> dict:
    return {
        "prompt": "test prompt",
        "parent_source": BASELINE,
        "log_text": "# log\n",
        "model": "test/model",
        "provider": None,
        "key_env_var": "TEST_KEY",
        "base_url": None,
        "api_key": "fake-key",
        "timeout_s": 60.0,
        "opencode_bin": str(stub),
        "models_cache_source": None,
    }


def test_research_round_happy_path(tmp_path: Path) -> None:
    stub = _stub_agent(tmp_path, "pass  # replaced below")
    # The stub edits the policy (comment only) and appends notes+verdict:
    stub.write_text(
        "#!/usr/bin/env python3\n"
        "text = open('evolve_me.py').read()\n"
        "open('evolve_me.py', 'w').write("
        "text.replace('# EVOLVE-START', '# EVOLVE-START\\n# stub tweak', 1))\n"
        "open('research_log.md', 'a').write("
        "'stub notes\\n## Verdict\\nVERDICT: SHIP\\nREASON: stub test\\n')\n",
        encoding="utf-8",
    )
    edited, appendix, verdict = launch_research_round(**_round_kwargs(stub))
    assert "# stub tweak" in edited
    assert "VERDICT: SHIP" in appendix
    assert verdict.ship is True
    assert verdict.reason == "stub test"


def test_research_round_rejects_third_file(tmp_path: Path) -> None:
    stub = _stub_agent(tmp_path, "open('scratch.txt', 'w').write('oops\\n')\n")
    with pytest.raises(research.RoundError, match="scratch.txt"):
        launch_research_round(**_round_kwargs(stub))


def test_research_round_rejects_rewritten_log(tmp_path: Path) -> None:
    stub = _stub_agent(tmp_path, "open('research_log.md', 'w').write('rewritten\\n')\n")
    with pytest.raises(research.RoundError, match="append-only"):
        launch_research_round(**_round_kwargs(stub))


def test_research_round_hold_without_verdict(tmp_path: Path) -> None:
    stub = _stub_agent(
        tmp_path, "open('research_log.md', 'a').write('no verdict here\\n')\n"
    )
    edited, _, verdict = launch_research_round(**_round_kwargs(stub))
    assert verdict.ship is False
    assert "evolve_me" in edited or "EvolvingPolicy" in edited
