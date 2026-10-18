"""Fight probe: does injecting fight orders beat pure expansion?

Agent nation (external, index 0) vs production Hard (index 1) on The Box,
idle human third party. Four scripted policies x N seeds, each to
completion: winner, ticks, injected-order count, total reward. Baseline is
always-expand (= Improved-Hard play); the question is whether any fight
policy wins worlds the baseline loses, or wins shared worlds faster.

Usage:
  uv run python analysis/probe_fight.py --seeds BOX-PROBE-A,BOX-PROBE-B --jobs 2
  uv run python analysis/probe_fight.py --jobs 6  # default 6 fresh seeds
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from openfrontbench.duel_env import COMMIT, EXPAND, RAID, DuelEnv
from sweep_single_entity import MAP_DIR, SPAWN

logger = logging.getLogger(__name__)

DEFAULT_SEEDS = [f"BOX-PROBE-{c}" for c in "ABCDEF"]


def policy_expand(_step: int, _obs: dict[str, Any]) -> int:
    return EXPAND


def policy_raid(_step: int, _obs: dict[str, Any]) -> int:
    return RAID


def policy_commit(_step: int, _obs: dict[str, Any]) -> int:
    return COMMIT


def policy_cycle(step: int, _obs: dict[str, Any]) -> int:
    return [EXPAND, RAID, EXPAND, COMMIT][step % 4]


POLICIES = {
    "expand": policy_expand,
    "raid": policy_raid,
    "commit": policy_commit,
    "cycle": policy_cycle,
}


def run_episode(seed: str, policy_name: str) -> dict[str, Any]:
    """Play one scripted episode to completion; never raises (errors are
    reported in the result so one bad episode cannot kill the probe)."""
    decide = POLICIES[policy_name]
    try:
        with DuelEnv(seed, map_dir=str(MAP_DIR), map_size="full", spawn=SPAWN) as env:
            env.reset()
            done = False
            step = 0
            total_reward = 0.0
            orders = 0
            obs: dict[str, Any] | None = None
            info: dict[str, Any] = {}
            while not done:
                action = decide(step, obs or {})
                orders += 1 if action != EXPAND else 0
                obs, reward, done, info = env.step(action)
                total_reward += reward
                step += 1
            assert obs is not None
            return {
                "seed": seed,
                "policy": policy_name,
                "winner": info["winner"],
                "agent_won": info["winner"] == obs["me"]["name"],
                "ticks": info["tick"],
                "orders": orders,
                "total_reward": round(total_reward, 1),
            }
    except Exception as exc:  # noqa: BLE001 — probe must survive bad episodes
        logger.exception("episode failed: %s/%s", seed, policy_name)
        return {"seed": seed, "policy": policy_name, "error": str(exc)}


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seeds",
        default=",".join(DEFAULT_SEEDS),
        help="comma-separated game ids (default: %(default)s)",
    )
    parser.add_argument(
        "--policies",
        default=",".join(POLICIES),
        help="comma-separated policies (default: %(default)s)",
    )
    parser.add_argument("--jobs", type=int, default=6)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent / "results" / "probe_fight.json",
    )
    args = parser.parse_args(argv)
    seeds = [s for s in args.seeds.split(",") if s]
    policies = [p for p in args.policies.split(",") if p in POLICIES]
    specs = [(s, p) for s in seeds for p in policies]
    results: list[dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(run_episode, s, p) for s, p in specs]
        for (seed, policy), future in zip(specs, futures):
            result = future.result()
            results.append(result)
            logger.info(result)
    payload = {
        "created": datetime.now(timezone.utc).isoformat(),
        "episodes": results,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=1))
    print(f"wrote {len(results)} episodes to {args.out}")
    return 0


if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parent.parent)
    sys.exit(main())
