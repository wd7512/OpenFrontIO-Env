"""Run play -> retro -> memory cycles.

Re-runnable: memories persist under the cycles root, version numbering
continues, and the ledger appends. Resume with the same command::

    uv run python scripts/run_cycle.py --cycles 3
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from openfrontbench.cycle import CAP_HIT_THRESHOLD, cap_after_cap_hits, run_cycle
from openfrontbench.live_smoke import (
    KEY_ENV_BY_PROVIDER,
    _default_models_cache,
    load_settings,
    run,
)
from openfrontbench.opencode_launcher import PROVIDER_BASE_URLS
from openfrontbench.paths import REPO_ROOT

logging.basicConfig(level=logging.INFO)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="play/retro/memory cycles")
    parser.add_argument("--cycles", type=int, default=3)
    parser.add_argument("--cycles-root", default="cycles")
    parser.add_argument("--env-file", default=".env.local")
    parser.add_argument("--max-decisions", type=int, default=150)
    parser.add_argument("--difficulty", default="easy")
    parser.add_argument("--coach-timeout", type=float, default=900)
    parser.add_argument(
        "--min-decisions",
        type=int,
        default=10,
        help="runs with fewer decisions (or provider crashes) are invalid: "
        "retried once, recorded, never coached",
    )
    parser.add_argument(
        "--memory-version",
        type=int,
        default=None,
        help="pin the played playbook to a version (variance/A-B runs); "
        "coaching still appends the next version",
    )
    parser.add_argument("--out-prefix", default=None)
    parser.add_argument(
        "--retro-only",
        default=None,
        help="run dir of a finished match; coach it into the next memory "
        "version without playing (seeds memory-v1 from history)",
    )
    args = parser.parse_args(argv)

    settings = load_settings(args.env_file)
    provider = (settings.get("OPENFRONT_PROVIDER") or "").strip()
    model = (settings.get("OPENFRONT_MODEL") or "").strip()
    key_env = KEY_ENV_BY_PROVIDER.get(provider, "OPENROUTER_API_KEY")
    api_key = (settings.get(key_env) or "").strip()
    if not api_key:
        raise SystemExit(f"missing key for {key_env!r}; refusing to start")
    cache = _default_models_cache()

    root = Path(args.cycles_root)
    if args.retro_only:
        from openfrontbench.cycle import coach_only

        version = coach_only(
            cycles_root=root,
            run_dir=args.retro_only,
            model=model,
            provider=provider,
            key_env_var=key_env,
            base_url=PROVIDER_BASE_URLS.get(provider),
            api_key=api_key,
            coach_timeout_s=args.coach_timeout,
            models_cache_source=cache,
        )
        print(f"memory-v{version}.md written")
        return 0
    cap = args.max_decisions
    cap_hits = 0
    for _ in range(args.cycles):
        import time

        stamp = time.strftime("%Y%m%d-%H%M")
        out = (
            Path(args.out_prefix).parent / f"{Path(args.out_prefix).name}-{stamp}"
            if args.out_prefix
            else REPO_ROOT / "raw" / f"openfront-cycle-{stamp}"
        )
        row = run_cycle(
            cycles_root=root,
            play_fn=run,
            play_kwargs={
                "env_file": args.env_file,
                "output": out,
                "timeout_s": 30000,
                "max_decisions": cap,
                "difficulty": args.difficulty,
                "models_cache_source": cache,
            },
            model=model,
            provider=provider,
            key_env_var=key_env,
            base_url=PROVIDER_BASE_URLS.get(provider),
            api_key=api_key,
            coach_timeout_s=args.coach_timeout,
            models_cache_source=cache,
            memory_version=args.memory_version,
            min_decisions=args.min_decisions,
        )
        logging.getLogger(__name__).info("cycle done: %s", row)
        if not row.get("valid"):
            logging.getLogger(__name__).warning(
                "cycle %s invalid (decisions=%s api_error=%s); not counted",
                row.get("cycle"),
                row.get("decisions"),
                row.get("api_error"),
            )
            continue
        if row.get("winner"):
            logging.getLogger(__name__).info("winner declared; stopping")
            break
        # Only a live player that ran out of ceiling earns a longer game;
        # a run eliminated at the ceiling proves nothing about stamina.
        if (row.get("decisions") or 0) >= cap and (row.get("tiles") or 0) > 0:
            cap_hits += 1
        new_cap, cap_hits = cap_after_cap_hits(cap_hits, cap)
        if new_cap != cap:
            logging.getLogger(__name__).info(
                "decision cap raised from %s to %s after %s ceiling finishes",
                cap,
                new_cap,
                CAP_HIT_THRESHOLD,
            )
            cap = new_cap
    return 0


if __name__ == "__main__":
    sys.exit(main())
