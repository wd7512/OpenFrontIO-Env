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

from openfront_mcp.cycle import run_cycle
from openfront_mcp.live_smoke import (
    KEY_ENV_BY_PROVIDER,
    _default_models_cache,
    load_settings,
    run,
)
from openfront_mcp.opencode_launcher import PROVIDER_BASE_URLS

logging.basicConfig(level=logging.INFO)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="play/retro/memory cycles")
    parser.add_argument("--cycles", type=int, default=3)
    parser.add_argument("--cycles-root", default="cycles")
    parser.add_argument("--env-file", default=".env.local")
    parser.add_argument("--scenario", default="solo")
    parser.add_argument("--max-decisions", type=int, default=150)
    parser.add_argument("--difficulty", default="easy")
    parser.add_argument("--coach-timeout", type=float, default=900)
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
        from openfront_mcp.cycle import coach_only

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
    for _ in range(args.cycles):
        import time

        stamp = time.strftime("%Y%m%d-%H%M")
        out = (
            Path(args.out_prefix).parent / f"{Path(args.out_prefix).name}-{stamp}"
            if args.out_prefix
            else Path(f"/Users/williamdennis/Downloads/openfront-cycle-{stamp}")
        )
        row = run_cycle(
            cycles_root=root,
            play_fn=run,
            play_kwargs={
                "env_file": args.env_file,
                "output": out,
                "timeout_s": 30000,
                "scenario": args.scenario,
                "max_decisions": args.max_decisions,
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
        )
        logging.getLogger(__name__).info("cycle done: %s", row)
        if row.get("winner"):
            logging.getLogger(__name__).info("winner declared; stopping")
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
