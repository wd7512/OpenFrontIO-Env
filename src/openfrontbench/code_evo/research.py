"""Research-log ledger and two-file round enforcement (autoresearch-style).

The coding agent may change exactly two files per round: the policy
script (``evolve_me.py``) and the research log (``research_log.md``,
append-only). Everything else — prompts, evaluator, registry, repo —
is harness-owned. Enforcement is post-hoc and deterministic: after the
agent exits, the harness diffs the work dir against a pre-round
snapshot, checks the log is still append-only, and checks the repo
``git status`` is unchanged. Violations reject the round.

The round verdict travels inside the log (no third file): the agent
ends its appended section with::

    ## Verdict
    VERDICT: SHIP
    REASON: one line on why this is worth the 8-spawn eval
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

LOG_FILENAME = "research_log.md"
POLICY_FILENAME = "evolve_me.py"

VERDICT_RE = re.compile(r"^VERDICT:\s*(SHIP|HOLD)\s*$", re.MULTILINE)
REASON_RE = re.compile(r"^REASON:\s*(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class Verdict:
    """Parsed round verdict: whether to spend the 8-spawn eval."""

    ship: bool
    reason: str


class RoundError(ValueError):
    """A research round broke the two-file contract or gave no verdict."""


def parse_verdict(log_text: str) -> Verdict:
    """Parse the last VERDICT block; HOLD when absent or unparseable."""
    verdicts = VERDICT_RE.findall(log_text)
    if not verdicts:
        return Verdict(ship=False, reason="no VERDICT trailer in log")
    reasons = REASON_RE.findall(log_text)
    return Verdict(
        ship=verdicts[-1] == "SHIP",
        reason=reasons[-1] if reasons else "no REASON line",
    )


def snapshot_files(work_dir: Path) -> dict[str, str]:
    """Map relative path -> sha256 for every file under *work_dir*."""
    snapshot: dict[str, str] = {}
    for path in sorted(work_dir.rglob("*")):
        if path.is_file() and not path.is_symlink():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            snapshot[str(path.relative_to(work_dir))] = digest
    return snapshot


def changed_files(before: dict[str, str], after: dict[str, str]) -> dict[str, str]:
    """New or modified files: relpath -> 'added' | 'modified'."""
    changed: dict[str, str] = {}
    for rel, digest in after.items():
        if rel not in before:
            changed[rel] = "added"
        elif before[rel] != digest:
            changed[rel] = "modified"
    return changed


def check_two_file_rule(work_dir: Path, before: dict[str, str], log_before: str) -> str:
    """Enforce the contract; return the agent's appended log section.

    Raises :class:`RoundError` when any file besides the policy script
    or the research log changed, or when the log is not append-only.
    """
    after = snapshot_files(work_dir)
    changed = changed_files(before, after)
    allowed = {POLICY_FILENAME, LOG_FILENAME}
    violations = {rel: kind for rel, kind in changed.items() if rel not in allowed}
    if violations:
        detail = ", ".join(
            f"{rel} ({kind})" for rel, kind in sorted(violations.items())
        )
        raise RoundError(f"round touched files outside the two-file rule: {detail}")
    log_path = work_dir / LOG_FILENAME
    if not log_path.is_file():
        raise RoundError("research log missing after round")
    log_after = log_path.read_text(encoding="utf-8")
    if not log_after.startswith(log_before):
        raise RoundError("research log is not append-only (history rewritten)")
    return log_after[len(log_before) :]


def git_status_snapshot(repo: Path) -> str:
    """Porcelain status of *repo* (empty string when clean)."""
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RoundError(f"git status failed: {result.stderr.strip()[:200]}")
    return result.stdout


def check_repo_untouched(repo: Path, before: str) -> None:
    """Raise when the agent's round changed anything in the repo."""
    after = git_status_snapshot(repo)
    if after != before:
        raise RoundError(f"repo changed during round:\n{after[:1000]}")


def header_for_iteration(
    iteration: int,
    parent_id: str | None,
    parent_mean: float | None,
    parent_spawns: str,
    best_mean: float | None,
    forced_eval: bool,
) -> str:
    """Harness-written log header opening one research round."""
    lines = [
        "",
        f"## Iteration {iteration}",
        f"parent: {parent_id} (mean {parent_mean:.0f})"
        if parent_mean is not None
        else "parent: none yet (baseline round)",
        f"parent per-spawn: {parent_spawns}",
        f"best so far: {best_mean:.0f}"
        if best_mean is not None
        else "best so far: none",
    ]
    if forced_eval:
        lines.append("forced eval this round (agent HOLD still evaluates).")
    lines.append("")
    lines.append("### Agent notes")
    return "\n".join(lines)
