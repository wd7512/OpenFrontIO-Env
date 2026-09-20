"""Evolve loop CLI: sample parents -> OpenCode codes -> evaluator scores.

One iteration: pick the best + one diverse entry from the program DB,
ask the isolated OpenCode coding agent (file tools only, no game MCP)
to improve ``evolve_me.py``, validate the edit, run the N-spawn
evaluator headless, and append the scored entry to the DB.

``--evaluate-only`` scores a policy file without any model call (smoke
path for CI and dry runs).
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import logging
import sys
import tempfile
from pathlib import Path
from typing import Any

from openfrontbench.code_evo import evaluator as _evaluator
from openfrontbench.code_evo import program_db, sampler
from openfrontbench.code_evo import research as _research
from openfrontbench.code_evo.evaluator import EvalConfig
from openfrontbench.code_evo.research import RoundError
from openfrontbench.code_evo.spawns import SpawnError, load_registry
from openfrontbench.experiment import write_experiment as _write_experiment
from openfrontbench.live_smoke import (
    KEY_ENV_BY_PROVIDER,
    _default_models_cache,
    load_settings,
)
from openfrontbench.opencode_launcher import (
    build_agent_command,
    build_child_env,
    build_config,
    check_managed_settings,
    prepare_run,
    run_bounded,
)
from openfrontbench.paths import REPO_ROOT

log = logging.getLogger(__name__)

EVOLVE_START = "# EVOLVE-START"
EVOLVE_END = "# EVOLVE-END"

ALLOWED_STDLIB = frozenset(
    {
        "collections",
        "dataclasses",
        "functools",
        "heapq",
        "itertools",
        "math",
        "random",
        "statistics",
        "typing",
    }
)

RESEARCH_AGENT_PROMPT = (
    "You are the OpenFrontBench research agent. Read research_log.md "
    "in your working directory first (the full lab notebook), then "
    "improve evolve_me.py between the EVOLVE markers and append your "
    "notes plus a VERDICT trailer to the log. The only files you may "
    "change are evolve_me.py and research_log.md: no shell, no network, "
    "no new files, nothing else touched."
)


class CandidateError(ValueError):
    """A candidate policy file violates the edit contract."""


def validate_candidate(path: Path) -> str:
    """Check markers, syntax, interface and imports; return file text."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise CandidateError(f"cannot read candidate {path}: {error}") from error
    if text.count(EVOLVE_START) != 1 or text.count(EVOLVE_END) != 1:
        raise CandidateError("candidate must contain each EVOLVE marker once")
    try:
        tree = ast.parse(text)
    except SyntaxError as error:
        raise CandidateError(f"candidate is not valid Python: {error}") from error
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] not in ALLOWED_STDLIB:
                    raise CandidateError(f"import not allowed: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = (node.module or "").split(".")[0]
            if module not in ALLOWED_STDLIB | {"openfrontbench", "__future__"}:
                raise CandidateError(f"import not allowed: {node.module}")
    if "class EvolvingPolicy" not in text or "def decide" not in text:
        raise CandidateError("candidate must define EvolvingPolicy.decide")
    return text


def launch_research_round(
    *,
    prompt: str,
    parent_source: str,
    log_text: str,
    model: str,
    provider: str | None,
    key_env_var: str,
    base_url: str | None,
    api_key: str,
    timeout_s: float,
    opencode_bin: str = "opencode",
    models_cache_source: Path | None = None,
) -> tuple[str, str, _research.Verdict]:
    """Run one isolated research round; return (policy, log_appendix, verdict).

    The work dir holds exactly the two agent-owned files (the parent
    policy and the cumulative log). After the agent exits, the two-file
    rule is enforced post-hoc and the repo must be untouched; the edited
    policy is validated like any candidate. Raises :class:`RoundError`
    (contract break) or :class:`CandidateError` (bad policy edit).
    """
    check_managed_settings()
    config = build_config(
        model=model,
        mcp=None,
        agent_name="research",
        agent_prompt=RESEARCH_AGENT_PROMPT,
        provider=provider,
        key_env_var=key_env_var,
        base_url=base_url,
        extra_allow=("glob", "grep"),
    )
    agent_root = Path(tempfile.mkdtemp(prefix="openfront-research-"))
    run = prepare_run(agent_root / "run", config)
    (run.work_dir / _research.POLICY_FILENAME).write_text(
        parent_source, encoding="utf-8"
    )
    (run.work_dir / _research.LOG_FILENAME).write_text(log_text, encoding="utf-8")
    files_before = _research.snapshot_files(run.work_dir)
    repo_before = _research.git_status_snapshot(REPO_ROOT)
    env = build_child_env(run=run, api_key=api_key, key_env_var=key_env_var)
    if models_cache_source is not None:
        from openfrontbench.opencode_launcher import seed_models_cache

        seed_models_cache(run, models_cache_source)
    argv = build_agent_command(
        prompt=prompt, agent_name="research", opencode_bin=opencode_bin
    )
    result = run_bounded(
        argv,
        env=env,
        cwd=run.work_dir,
        timeout_s=timeout_s,
        events_path=run.events_file,
        secrets=(api_key,),
    )
    if result.timed_out:
        raise RoundError("research agent timed out")
    if result.returncode != 0:
        raise RoundError(
            f"research agent exited {result.returncode}: {result.stderr.strip()[:300]}"
        )
    try:
        _research.check_repo_untouched(REPO_ROOT, repo_before)
    except RoundError as error:
        raise RoundError(str(error)) from error
    try:
        appendix = _research.check_two_file_rule(run.work_dir, files_before, log_text)
    except RoundError as error:
        raise RoundError(str(error)) from error
    edited_path = run.work_dir / _research.POLICY_FILENAME
    if not edited_path.is_file():
        raise RoundError("research agent did not leave evolve_me.py")
    edited = validate_candidate(edited_path)
    verdict = _research.parse_verdict(log_text + appendix)
    return edited, appendix, verdict


def _append_log(log_path: Path, text: str) -> str:
    """Append *text* to the master log; return the full new log text."""
    previous = log_path.read_text(encoding="utf-8") if log_path.is_file() else ""
    log_path.write_text(previous + text, encoding="utf-8")
    return previous + text


def _results_block(
    entry_id: str, result: dict[str, Any], wall_s: float | None = None
) -> str:
    """Harness-written log section recording one finished evaluation."""
    lines = [
        "",
        f"### Eval results ({entry_id})",
        f"mean={result['mean_score']:.0f} min={result['min_score']:.0f} "
        f"max={result['max_score']:.0f} wins={result['wins']}",
    ]
    for spawn in result["spawns"]:
        lines.append(
            f"- {spawn['spawn_id']}: score={spawn['score']:.0f} "
            f"peak={spawn['tiles_peak']} final={spawn['final_tiles']} "
            f"ticks={spawn['ticks']} winner={spawn['winner']} "
            f"errors={spawn['policy_errors']} tile={spawn.get('spawn_tile')} "
            f"world={spawn.get('game_id')} out={spawn.get('outcome')} "
            f"tpeak={spawn.get('troops_peak')} gpeak={spawn.get('gold_peak')} "
            f"city={spawn.get('city_ever')}"
        )
    if wall_s is not None:
        lines.append(f"eval wall: {wall_s:.0f}s")
    lines.append("")
    return "\n".join(lines)


def _log_preamble(
    run_name: str,
    registry: Any,
    eval_config: EvalConfig,
    iterations: int,
    jobs: int,
    world_scheme: str = "compact",
) -> str:
    spawns = ", ".join(f"{s.id}=({s.x},{s.y})" for s in registry.spawns)
    return (
        f"# Research log: {run_name}\n"
        f"map={registry.map} spawns: {spawns}\n"
        f"nations={eval_config.nations} tribes={eval_config.tribes} "
        f"difficulty={eval_config.difficulty} max_ticks={eval_config.max_ticks} "
        f"iterations={iterations} jobs={jobs} world_scheme={world_scheme}\n"
        f"spawns registry sha256: {registry.sha256}\n"
        "Score per spawn = tiles_peak + 5 * survival_ticks (+500000 win); "
        "candidate score = mean over spawns.\n"
    )


def _resolve_model(
    env_file: str,
    model_override: str | None = None,
    provider_override: str | None = None,
) -> tuple[str, str | None, str, str]:
    settings = load_settings(env_file)
    provider = (
        provider_override or (settings.get("OPENFRONT_PROVIDER") or "").strip() or None
    )
    model = model_override or (settings.get("OPENFRONT_MODEL") or "").strip()
    if not model:
        raise ValueError("OPENFRONT_MODEL is required in the env file")
    key_env = KEY_ENV_BY_PROVIDER.get(provider or "", "OPENROUTER_API_KEY")
    api_key = (settings.get(key_env) or "").strip()
    if not api_key:
        raise ValueError(f"missing key for {key_env!r}; refusing to start")
    return model, provider, key_env, api_key


def run_evolution(
    *,
    spawns_path: Path,
    output: Path,
    policy_path: Path,
    iterations: int,
    eval_config: EvalConfig,
    model: str,
    provider: str | None,
    key_env_var: str,
    base_url: str | None,
    api_key: str,
    agent_timeout_s: float,
    models_cache_source: Path | None = None,
    prompts_dir: Path | None = None,
    jobs: int = 1,
    world_scheme: str = "compact",
) -> list[dict[str, Any]]:
    """Run *iterations* evolve rounds; return the appended DB entries."""
    try:
        registry = load_registry(spawns_path)
    except SpawnError as error:
        raise ValueError(str(error)) from error
    output.mkdir(parents=True, exist_ok=True)
    db_path = output / "program_db.jsonl"
    _write_experiment(
        output,
        name=output.name,
        kind="code-evo",
        config={
            "spawns": str(spawns_path),
            "iterations": iterations,
            "nations": eval_config.nations,
            "tribes": eval_config.tribes,
            "difficulty": eval_config.difficulty,
            "max_ticks": eval_config.max_ticks,
            "world_scheme": world_scheme,
        },
    )
    template = sampler.load_template(
        prompts_dir or (REPO_ROOT / "prompts"), name="code_evo_research"
    )
    baseline_source = validate_candidate(policy_path)
    log_path = output / _research.LOG_FILENAME
    _append_log(
        log_path,
        _log_preamble(
            output.name, registry, eval_config, iterations, jobs, world_scheme
        ),
    )
    appended: list[dict[str, Any]] = []
    parent_source = baseline_source
    since_improvement = 0
    for iteration in range(iterations):
        entries = program_db.load_entries(db_path)
        best = program_db.best_entry(entries)
        best_mean = float(best["mean_score"]) if best is not None else None
        if best is None:
            episode_dir = output / "iter_0_baseline"
            result = _evaluator.evaluate_candidate(
                policy_path,
                registry,
                eval_config,
                episode_dir,
                write_experiment_manifest=False,
                game_id_prefix=output.name,
                jobs=jobs,
                world_scheme=world_scheme,
            )
            entry = {
                "id": "iter_0_baseline",
                "parent_id": None,
                "policy_sha256": result["policy_sha256"],
                "mean_score": result["mean_score"],
                "spawns": result["spawns"],
                "source": baseline_source,
                "verdict": "BASELINE",
            }
            program_db.append_entry(db_path, entry)
            appended.append(entry)
            _append_log(
                log_path,
                "## Iteration 0 (baseline, no agent)\n"
                + _results_block("iter_0_baseline", result, result["wall_s"]),
            )
            parent_source = baseline_source
            log.info("baseline scored: %.0f", result["mean_score"])
            continue
        diverse = program_db.diverse_entry(
            entries, str(best.get("policy_sha256")), seed=iteration
        )
        if isinstance(best.get("source"), str):
            parent_source = best["source"]
        diverse_source = None
        diverse_id: str | None = None
        if diverse is not None and isinstance(diverse.get("source"), str):
            diverse_source = diverse["source"]
            diverse_id = str(diverse.get("id"))
        if since_improvement >= 6 and diverse_source is not None:
            parent_source = diverse_source
            _append_log(
                log_path,
                f"## Iteration {iteration} (stall switch: no improvement in "
                f"{since_improvement}, parenting from diverse {diverse_id})\n",
            )
            since_improvement = 0
        prompt = sampler.render_coding_prompt(
            template,
            best,
            diverse,
            parent_source,
            diverse_source,
        )
        forced_eval = iteration % 4 == 3
        header = _research.header_for_iteration(
            iteration,
            str(best.get("id")),
            best_mean,
            sampler._summarize(best),
            best_mean,
            forced_eval,
        )
        master_text = _append_log(log_path, header)
        try:
            edited, appendix, verdict = launch_research_round(
                prompt=prompt,
                parent_source=parent_source,
                log_text=master_text,
                model=model,
                provider=provider,
                key_env_var=key_env_var,
                base_url=base_url,
                api_key=api_key,
                timeout_s=agent_timeout_s,
                models_cache_source=models_cache_source,
            )
        except (RoundError, CandidateError) as error:
            _append_log(log_path, f"\nRound rejected: {error}\n")
            log.warning("iteration %d round rejected: %s", iteration, error)
            continue
        _append_log(log_path, appendix)
        should_eval = verdict.ship or forced_eval
        _append_log(
            log_path,
            f"\nVerdict: {'SHIP' if verdict.ship else 'HOLD'} "
            f"({'forced eval' if forced_eval and not verdict.ship else verdict.reason})\n",
        )
        if not should_eval:
            entry = {
                "id": f"iter_{iteration}",
                "parent_id": best.get("id"),
                "policy_sha256": None,
                "mean_score": None,
                "spawns": [],
                "source": edited,
                "verdict": "HOLD",
            }
            program_db.append_entry(db_path, entry)
            appended.append(entry)
            log.info("iteration %d HOLD: %s", iteration, verdict.reason)
            continue
        candidate_path = output / f"iter_{iteration}" / "evolve_me.py"
        candidate_path.parent.mkdir(parents=True, exist_ok=True)
        candidate_path.write_text(edited, encoding="utf-8")
        parent_path = output / f"iter_{iteration}" / "parent_evolve_me.py"
        parent_path.write_text(parent_source, encoding="utf-8")
        diverged, probe_detail = _evaluator.probe_divergence(
            candidate_path,
            parent_path,
            registry,
            eval_config,
            output.name,
            world_scheme=world_scheme,
        )
        _append_log(log_path, f"\nDivergence probe: {probe_detail}.\n")
        log.info("iteration %d probe: %s", iteration, probe_detail)
        if not diverged:
            entry = {
                "id": f"iter_{iteration}",
                "parent_id": best.get("id"),
                "policy_sha256": hashlib.sha256(edited.encode("utf-8")).hexdigest(),
                "mean_score": None,
                "spawns": [],
                "source": edited,
                "verdict": "HOLD",
                "note": f"divergence probe: {probe_detail}",
            }
            program_db.append_entry(db_path, entry)
            appended.append(entry)
            continue
        episode_dir = output / f"iter_{iteration}_eval"
        result = _evaluator.evaluate_candidate(
            candidate_path,
            registry,
            eval_config,
            episode_dir,
            write_experiment_manifest=False,
            game_id_prefix=output.name,
            jobs=jobs,
            world_scheme=world_scheme,
        )
        entry = {
            "id": f"iter_{iteration}",
            "parent_id": best.get("id"),
            "policy_sha256": result["policy_sha256"],
            "mean_score": result["mean_score"],
            "spawns": result["spawns"],
            "source": edited,
            "verdict": "FORCED" if forced_eval and not verdict.ship else "SHIP",
        }
        program_db.append_entry(db_path, entry)
        appended.append(entry)
        _append_log(
            log_path, _results_block(f"iter_{iteration}", result, result["wall_s"])
        )
        if best_mean is not None and result["mean_score"] > best_mean:
            since_improvement = 0
            log.info("iteration %d improved: %.0f", iteration, result["mean_score"])
        else:
            since_improvement += 1
    return appended


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(
        prog="python -m openfrontbench.code_evo.evolve",
        description="Evolve the behavior policy over fixed spawns.",
    )
    parser.add_argument(
        "--spawns", required=True, type=Path, help="spawn registry JSON"
    )
    parser.add_argument("--output", required=True, type=Path, help="output directory")
    parser.add_argument(
        "--policy",
        type=Path,
        default=REPO_ROOT / "src" / "openfrontbench" / "policies" / "evolve_me.py",
        help="baseline policy file",
    )
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--nations", type=int, default=52)
    parser.add_argument("--tribes", type=int, default=400)
    parser.add_argument("--difficulty", default="medium")
    parser.add_argument("--max-ticks", type=int, default=_evaluator.MAX_TICKS)
    parser.add_argument("--env-file", default=".env.local")
    parser.add_argument(
        "--model",
        default=None,
        help="coding-agent model override (default: OPENFRONT_MODEL)",
    )
    parser.add_argument(
        "--provider",
        default=None,
        help="provider override (default: OPENFRONT_PROVIDER)",
    )
    parser.add_argument("--agent-timeout", type=float, default=1200.0)
    parser.add_argument(
        "--jobs",
        type=int,
        default=1,
        help="parallel spawn games per candidate (spawn-context processes)",
    )
    parser.add_argument(
        "--evaluate-only",
        action="store_true",
        help="score --policy without any model call",
    )
    parser.add_argument(
        "--world-scheme",
        default="compact",
        help="world-id derivation: 'compact' (8-alnum, tapes replay "
        "faithfully) or 'legacy' (frozen 32-char ids, reproduces "
        "pre-compact worlds but tapes replay expands only)",
    )
    args = parser.parse_args(argv)

    if args.iterations < 1:
        log.error("iterations must be >= 1")
        return 2
    try:
        registry = load_registry(args.spawns)
    except SpawnError as error:
        log.error("spawn registry error: %s", error)
        return 2
    eval_config = EvalConfig(
        nations=args.nations,
        tribes=args.tribes,
        difficulty=args.difficulty,
        max_ticks=args.max_ticks,
    )
    if args.difficulty not in ("easy", "medium", "hard", "impossible"):
        log.error("bad difficulty: %s", args.difficulty)
        return 2

    if args.evaluate_only:
        try:
            validate_candidate(args.policy)
        except CandidateError as error:
            log.error("candidate error: %s", error)
            return 2
        args.output.mkdir(parents=True, exist_ok=True)
        result = _evaluator.evaluate_candidate(
            args.policy,
            registry,
            eval_config,
            args.output / "eval",
            game_id_prefix=args.output.name,
            jobs=args.jobs,
            world_scheme=args.world_scheme,
        )
        log.info(
            "evaluate-only: mean=%.0f min=%.0f wins=%d",
            result["mean_score"],
            result["min_score"],
            result["wins"],
        )
        return 0

    try:
        model, provider, key_env_var, api_key = _resolve_model(
            args.env_file, args.model, args.provider
        )
    except ValueError as error:
        log.error("%s", error)
        return 2
    from openfrontbench.opencode_launcher import PROVIDER_BASE_URLS

    appended = run_evolution(
        spawns_path=args.spawns,
        output=args.output,
        policy_path=args.policy,
        iterations=args.iterations,
        eval_config=eval_config,
        model=model,
        provider=provider,
        key_env_var=key_env_var,
        base_url=PROVIDER_BASE_URLS.get(provider or ""),
        api_key=api_key,
        agent_timeout_s=args.agent_timeout,
        models_cache_source=_default_models_cache(),
        jobs=args.jobs,
        world_scheme=args.world_scheme,
    )
    log.info("evolution complete: %d entries", len(appended))
    return 0


if __name__ == "__main__":
    sys.exit(main())
