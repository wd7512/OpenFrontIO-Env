"""Play -> retro -> memory cycle.

One cycle: a blind player matches via the MCP tools, then a sighted coach
(reads the run bundle + curated sources, no play tools) writes the next
version of the strategy playbook. The next player gets the latest playbook
in its prompt.

The coach never touches the repository: it works in an isolated temp dir on
copies. The player never sees code: notes are the only channel.
"""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable, Mapping

from openfront_mcp import opencode_launcher as ol
from openfront_mcp.paths import REPO_ROOT

log = logging.getLogger(__name__)

# Curated sources the coach may study: the engine mechanics that decide
# battles, boats and growth, plus the adapter surface the player actually
# drives. Small on purpose: the whole repo would blow the token budget this
# cycle exists to control.
COACH_SOURCES: tuple[str, ...] = (
    # attackLogic/attackAmount/maxTroops: troop-loss math and tempo.
    "vendor/OpenFrontIO/src/core/configuration/Config.ts",
    # Retreat malus and the per-tile combat loop.
    "vendor/OpenFrontIO/src/core/execution/AttackExecution.ts",
    # Transport ships: cost, capacity, landing and retreat rules.
    "vendor/OpenFrontIO/src/core/execution/TransportShipExecution.ts",
    "vendor/OpenFrontIO/src/core/game/TransportShipUtils.ts",
    # Nation/bot cadence, reserve/trigger gates, dogpile and retaliation
    # targeting, and the engine's own 4x bot-attack sizing.
    "vendor/OpenFrontIO/src/core/execution/utils/AiAttackBehavior.ts",
    # Per-nation attack clock and structure-check cadence.
    "vendor/OpenFrontIO/src/core/execution/NationExecution.ts",
    # Alliance accept/reject thresholds, relation windows, betrayal rules.
    "vendor/OpenFrontIO/src/core/execution/nation/NationAllianceBehavior.ts",
    # What nations build when: defense-post trigger (land attacks only),
    # city/port/SAM/silo pacing.
    "vendor/OpenFrontIO/src/core/execution/nation/NationStructureBehavior.ts",
    # Tribes are bots: their clock, trigger ratio and structure deletion.
    "vendor/OpenFrontIO/src/core/execution/TribeExecution.ts",
    # Per-tick gold and troop regen, relation decay.
    "vendor/OpenFrontIO/src/core/execution/PlayerExecution.ts",
    # Adapter surface: what orders exist and how they reach the engine.
    "engine/worker.ts",
    "src/openfront_mcp/session.py",
)

MEMORY_FILENAME = "memory.md"
BUNDLE_FILENAMES: tuple[str, ...] = ("live_result.json", "record.json")

# A run that stops at the decision ceiling without a winner proves the player
# can still play: after five of those at the same ceiling, allow longer games.
CAP_HIT_THRESHOLD = 5
CAP_HIT_STEP = 100


def cap_after_cap_hits(cap_hits: int, cap: int) -> tuple[int, int]:
    """Escalate the decision ceiling every ``CAP_HIT_THRESHOLD`` ceiling ends.

    Returns ``(cap, cap_hits)``: the new ceiling and the counter reset state.
    """
    if cap_hits >= CAP_HIT_THRESHOLD:
        return cap + CAP_HIT_STEP, 0
    return cap, cap_hits


class MemoryStore:
    """Versioned strategy playbook: memory-v1.md, memory-v2.md, ..."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, version: int) -> Path:
        return self.root / f"memory-v{version}.md"

    def _versions(self) -> list[int]:
        out = []
        for child in self.root.glob("memory-v*.md"):
            try:
                out.append(int(child.stem.split("-v")[1]))
            except (IndexError, ValueError):
                continue
        return sorted(out)

    def latest(self) -> str | None:
        versions = self._versions()
        if not versions:
            return None
        return self._path(versions[-1]).read_text(encoding="utf-8")

    def save(self, text: str) -> int:
        if not text or not text.strip():
            raise ValueError("refusing to store empty memory")
        version = (self._versions()[-1] if self._versions() else 0) + 1
        self._path(version).write_text(text.strip() + "\n", encoding="utf-8")
        return version


def _compact_tape(tape: Mapping[str, Any]) -> dict[str, Any]:
    """Keep tape shape but drop empty turns (thousands of them)."""
    turns = tape.get("turns")
    if not isinstance(turns, list):
        return dict(tape)
    compact = {k: v for k, v in tape.items() if k != "turns"}
    compact["turns"] = [t for t in turns if t.get("intents")]
    return compact


def assemble_coach_bundle(
    run_dir: Path | str,
    sources: list[Path | str],
    dest: Path | str,
    max_chars: int = 320_000,
) -> list[str]:
    """Copy run outputs + curated sources into the coach work dir.

    Returns the copied file names. Tapes are compacted. Source space is
    split proportionally to file size so a long file (Config.ts) is not
    cut off before its decisive section while a short one goes entire; all
    sources fit whole whenever the total stays inside the budget.
    """
    run_path = Path(run_dir)
    dest_path = Path(dest)
    dest_path.mkdir(parents=True, exist_ok=True)
    names: list[str] = []
    for name in BUNDLE_FILENAMES:
        src = run_path / name
        if not src.is_file():
            continue
        text = src.read_text(encoding="utf-8")
        if name == "record.json":
            try:
                text = json.dumps(_compact_tape(json.loads(text)))
            except ValueError:
                pass
        (dest_path / name).write_text(text[:max_chars], encoding="utf-8")
        names.append(name)
    loaded: list[tuple[Path, str]] = []
    for src in sources:
        src_path = Path(src)
        if not src_path.is_file():
            continue
        loaded.append((src_path, src_path.read_text(encoding="utf-8")))
    budget = max_chars - sum((dest_path / name).stat().st_size for name in names)
    total = sum(len(text) for _, text in loaded) or 1
    for src_path, text in loaded:
        share = max(2_000, budget * len(text) // total)
        (dest_path / src_path.name).write_text(text[:share], encoding="utf-8")
        names.append(src_path.name)
    return names


def build_coach_prompt(
    bundle_files: list[str], output_name: str, has_previous: bool = False
) -> str:
    files = ", ".join(bundle_files)
    previous = (
        "previous_playbook.md is the playbook the player used in this match; "
        "evolve it — keep what still holds, correct or drop what the tape "
        "contradicts, and fold in what this match teaches. "
        if has_previous
        else ""
    )
    return (
        "You are the strategy coach for a solo OpenFront agent. Read these "
        f"files in your working directory: {files}. "
        "live_result.json is the final match state, record.json is the taped "
        "orders, and the rest are engine and adapter sources. "
        f"{previous}"
        "Mine the engine source for the mechanics behind battles, boats and "
        "growth (attackLogic, attackAmount and maxTroops in Config.ts; "
        "AttackExecution.ts; TransportShipExecution.ts and "
        "TransportShipUtils.ts) and for the timing behind them (the nation "
        "and tribe cadence, reserve/trigger gates, retaliation, alliance "
        "thresholds and structure pacing in utils/AiAttackBehavior.ts, "
        "NationExecution.ts, nation/NationAllianceBehavior.ts, "
        "nation/NationStructureBehavior.ts, TribeExecution.ts and "
        "PlayerExecution.ts). The player acts once per decision (50 ticks = "
        "5 s) and can read target troops and tiles for nations, bordering "
        "tribes and boat targets, plus its own incoming attacks and every "
        "rival's incoming_troops (pressure from others). Write rules it can "
        "act on with exactly those fields. "
        "Two sections are mandatory. (1) A short 'When to act' set of "
        "conditional rules: rival refill cadence and the counter window "
        "right after they spend, forced retaliation, when alliances are "
        "accepted (threat overrides relation), when defense posts appear "
        "(land attacks only) and how boats avoid triggering them, and when "
        "incoming_troops marks a real dogpile target. (2) An 'Attack sizing' "
        "rule set: never a fixed share — derive every size from observable "
        "quantities (target troops, tiles, density, terrain) with the "
        "exchange-rate math, including worked examples for tribes, nations "
        "and neutral land. "
        "Read the tape critically: was force over-committed, were transport "
        "ships used, did expansion stall against water, did the player act "
        "on the timing windows? "
        f"Write the next player's playbook to {output_name}: a short general "
        "ethos, not a match report — durable principles and decision rules "
        "that hold in any run of this format. No board-state recap, no long "
        "stat lists, no narrative; a few engine-accurate thresholds are "
        "welcome where they make a rule precise, and keep the whole thing "
        "under 60 lines. The next player sees this text and nothing else, so "
        "it must stand alone. No code, no match tools, no edits outside this "
        "directory. Then stop."
    )


def launch_coach(
    *,
    run_root: Path | str,
    model: str,
    provider: str,
    key_env_var: str,
    base_url: str | None,
    api_key: str,
    prompt: str,
    timeout_s: float,
    bundle_files: Mapping[str, Path | str] | None = None,
    opencode_bin: str = "opencode",
    base_env: Mapping[str, str] | None = None,
    models_cache_source: Path | str | None = None,
) -> ol.LaunchResult:
    """Run one isolated coach session (file tools only, no match tools)."""
    if api_key is None or not str(api_key).strip():
        raise ol.MissingApiKeyError(
            f"missing API key for {key_env_var!r}; refusing to start the coach"
        )
    config = ol.build_config(
        model=model,
        mcp=None,
        agent_name="coach",
        agent_prompt="Strategy coach: read local files, write memory notes.",
        provider=provider,
        key_env_var=key_env_var,
        base_url=base_url,
    )
    run = ol.prepare_run(run_root, config)
    if models_cache_source is not None:
        ol.seed_models_cache(run, models_cache_source)
    for name, src in (bundle_files or {}).items():
        shutil.copy(Path(src), run.work_dir / name)
    env = ol.build_child_env(
        run=run, api_key=api_key, key_env_var=key_env_var, base_env=base_env
    )
    argv = ol.build_agent_command(
        prompt=prompt, agent_name="coach", opencode_bin=opencode_bin
    )
    process = ol.run_bounded(
        argv,
        env=env,
        cwd=run.work_dir,
        timeout_s=timeout_s,
        events_path=run.events_file,
        secrets=(api_key,),
    )
    return ol.LaunchResult(
        run=run, config=config, resolved_config=None, process=process
    )


def append_ledger(ledger: Path | str, row: Mapping[str, Any]) -> None:
    path = Path(ledger)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(row)) + "\n")


class CycleSafetyError(RuntimeError):
    """The coach touched repository paths outside its allowance."""


def _git_status_lines(repo: Path | str) -> set[str]:
    """Raw ``git status --porcelain`` lines (empty set if git fails)."""
    import subprocess

    proc = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(repo),
    )
    if proc.returncode != 0:
        raise CycleSafetyError(f"git status failed: {proc.stderr[-500:]}")
    return set(proc.stdout.splitlines())


def check_repo_clean(repo: Path | str, baseline: set[str] | None = None) -> None:
    """Fail if the working tree gained ANY change during the coach window.

    The coach works on copies in a temp dir and its file tools accept
    absolute paths, so this is the backstop against it reaching into the
    repo — including ``cycles/`` itself, where a stray write could silently
    rewrite a memory file or the ledger. ``baseline`` is the status
    snapshot from before the coach ran, so pre-existing dirt is ignored.
    Safe to enforce strictly: ``coach_only`` saves the next memory version
    only after this check passes, and play artifacts land in gitignored
    ``raw/``, which never appears in ``git status``.
    """
    baseline = baseline or set()
    bad = sorted(_git_status_lines(repo) - baseline)
    if bad:
        raise CycleSafetyError("coach touched the repository: " + "; ".join(bad[:5]))


def coach_only(
    *,
    cycles_root: Path | str,
    run_dir: Path | str,
    model: str,
    provider: str,
    key_env_var: str,
    base_url: str | None,
    api_key: str,
    coach_timeout_s: float = 900,
    models_cache_source: Path | str | None = None,
) -> int:
    """Coach one finished match into the next memory version. No play."""
    root = Path(cycles_root)
    store = MemoryStore(root / "memories")
    out_dir = Path(str(run_dir))
    if not out_dir.is_dir():
        raise ValueError(f"run dir not found: {out_dir}")
    baseline = _git_status_lines(REPO_ROOT)
    coach_root = Path(tempfile.mkdtemp(prefix="openfront-coach-"))
    staging = coach_root / "staging"
    names = assemble_coach_bundle(
        out_dir, [REPO_ROOT / s for s in COACH_SOURCES], staging
    )
    previous = store.latest()
    has_previous = bool(previous)
    if previous:
        (staging / "previous_playbook.md").write_text(previous, encoding="utf-8")
        names.append("previous_playbook.md")
    launched = launch_coach(
        run_root=coach_root / "agent",
        model=model,
        provider=provider,
        key_env_var=key_env_var,
        base_url=base_url,
        api_key=api_key,
        prompt=build_coach_prompt(names, MEMORY_FILENAME, has_previous),
        timeout_s=coach_timeout_s,
        bundle_files={name: staging / name for name in names},
        models_cache_source=models_cache_source,
    )
    note = (launched.run.work_dir / MEMORY_FILENAME).read_text(encoding="utf-8")
    check_repo_clean(REPO_ROOT, baseline)
    return store.save(note)


def run_cycle(
    *,
    cycles_root: Path | str,
    play_fn: Callable[..., dict[str, Any]],
    play_kwargs: Mapping[str, Any],
    model: str,
    provider: str,
    key_env_var: str,
    base_url: str | None,
    api_key: str,
    coach_timeout_s: float = 900,
    models_cache_source: Path | str | None = None,
) -> dict[str, Any]:
    """Play one match with the latest memory, then coach the next version."""
    root = Path(cycles_root)
    store = MemoryStore(root / "memories")
    memory = store.latest()
    kwargs = dict(play_kwargs)
    if memory:
        kwargs["memory"] = memory
    played = play_fn(**kwargs)
    summary = played.get("summary", {})
    out_dir = Path(str(kwargs.get("output", "")))
    version: int | None = None
    if out_dir.is_dir():
        version = coach_only(
            cycles_root=root,
            run_dir=out_dir,
            model=model,
            provider=provider,
            key_env_var=key_env_var,
            base_url=base_url,
            api_key=api_key,
            coach_timeout_s=coach_timeout_s,
            models_cache_source=models_cache_source,
        )
    row = {
        "cycle": (store._versions()[-1] if store._versions() else 0),
        "tiles": (summary.get("final_human") or {}).get("tiles"),
        "troops": (summary.get("final_human") or {}).get("troops"),
        "winner": summary.get("winner"),
        "decisions": len(summary.get("decisions", [])),
        "memory_version": version,
        "model": model,
        "max_decisions": kwargs.get("max_decisions"),
    }
    append_ledger(root / "ledger.jsonl", row)
    return row
