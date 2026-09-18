"""Play -> retro -> memory cycle.

One cycle: a blind player matches via the MCP tools, then a sighted coach
(reads the run bundle + curated sources, no play tools) writes versioned
strategy notes. The next player gets the latest notes in its prompt.

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

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Curated sources the coach may study. Small on purpose: the whole repo
# would blow the token budget this cycle exists to control.
COACH_SOURCES: tuple[str, ...] = (
    "engine/worker.ts",
    "src/openfront_mcp/session.py",
)

MEMORY_FILENAME = "memory.md"
BUNDLE_FILENAMES: tuple[str, ...] = ("live_result.json", "record.json")


class MemoryStore:
    """Versioned strategy notes: memory-v1.md, memory-v2.md, ..."""

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
    max_chars: int = 60_000,
) -> list[str]:
    """Copy run outputs + curated sources into the coach work dir.

    Returns the copied file names. Tapes are compacted; sources are
    truncated to share the budget.
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
    per_source = max(
        4_000, (max_chars - sum(len(n) for n in names)) // max(1, len(sources))
    )
    for src in sources:
        src_path = Path(src)
        if not src_path.is_file():
            continue
        (dest_path / src_path.name).write_text(
            src_path.read_text(encoding="utf-8")[:per_source],
            encoding="utf-8",
        )
        names.append(src_path.name)
    return names


def build_coach_prompt(bundle_files: list[str], output_name: str) -> str:
    files = ", ".join(bundle_files)
    return (
        "You are a strategy coach reviewing one completed match. "
        f"Read these files in your working directory: {files}. "
        "The result file holds the final score and the player notes; "
        "the record holds the taped orders; other files are the engine "
        "and adapter sources behind the match. "
        "Write concise strategy notes for the NEXT player of the same "
        "format: what won tiles, what bled troops, when to strike, what "
        "to never repeat. Concrete numbers from this match beat general "
        "advice. No code, no tool calls to any match, no edits to anything "
        f"outside this directory. Write the notes to {output_name} and stop."
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
    """Fail if the working tree gained changes outside ``cycles/``.

    The coach works on copies in a temp dir, but its file tools accept
    absolute paths — this is the backstop. ``baseline`` is the status
    snapshot from before the coach ran, so pre-existing dirt is ignored;
    only NEW entries outside ``cycles/`` fail the cycle loudly.
    """
    baseline = baseline or set()
    bad = []
    for line in _git_status_lines(repo) - baseline:
        path = line[3:].strip().strip('"')
        if not path.startswith("cycles/"):
            bad.append(line)
    if bad:
        raise CycleSafetyError(
            "coach touched paths outside cycles/: " + "; ".join(bad[:5])
        )


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
    launched = launch_coach(
        run_root=coach_root / "agent",
        model=model,
        provider=provider,
        key_env_var=key_env_var,
        base_url=base_url,
        api_key=api_key,
        prompt=build_coach_prompt(names, MEMORY_FILENAME),
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
    }
    append_ledger(root / "ledger.jsonl", row)
    return row
