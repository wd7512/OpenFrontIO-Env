"""Tribe-farming confirmation (phase 2): the derived farm-p4 policy vs the
production-Hard race time on paired Box seeds.

Pure race, no rival nations: 1 external nation vs N tribes, human idle.
farm-p4 is PINNED by derivation (analysis/analytical_model.py kill model
plus production's AiAttackBehavior constants), not swept:

- cadence 52 (= Hard attack loop 45-60 ticks; phase-1 decision step)
- enclosed tribes first (token 2% poke; cluster deletion + <100 flip)
- then density (troops/tiles) ascending — production's sort
- tranche min(4x target, budget), budget = troops - 0.35*cap - sent
- skip fronts below 2x target; up to 3 parallel fronts
- retain >= 75% of the strongest observed other nation (troopSendCap)

The TN autopilot keeps expanding on the same ticks (production alternates
TN-or-bots per attack tick; we do both). Baselines: ``expand`` (=
Improved-Hard, no orders) and ``production`` (Hard's own race time — the
number to beat).

Usage:
  uv run python analysis/sweep_tribes.py --tribes 20 --jobs 6
  uv run python analysis/sweep_tribes.py --tribes 100 --policies farm-p4 --jobs 6
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

from openfrontbench.engine import EngineWorker
from sweep_single_entity import MAP_DIR, SPAWN
from analytical_model import (
    FARM_CADENCE,
    FARM_FORCE_MULT,
    FARM_PARALLEL,
    FARM_RESERVE,
    FARM_RETAIN,
    FARM_SKIP_MULT,
)

logger = logging.getLogger(__name__)

DEFAULT_SEEDS = [f"BOX-TRIBE-{c}" for c in "ABCDE"]
MAX_TICKS = 60000
ANNEX_SHARE = 0.02  # token poke on enclosed tribes (cluster deletion + flip)


def _alive_tribes(obs: dict[str, Any]) -> list[dict[str, Any]]:
    return [t for t in obs["tribes"] if t["alive"]]


def _bordering(obs: dict[str, Any]) -> list[dict[str, Any]]:
    return [t for t in _alive_tribes(obs) if t["bordersMe"]]


def _density(tribe: dict[str, Any]) -> float:
    """Production's bot sort key: troops per tile (attackBots)."""
    return float(tribe["troops"]) / max(1.0, float(tribe["tiles"]))


def run_episode(seed: str, tribes: int, policy: str) -> dict[str, Any]:
    """Play one farming episode to completion (or the tick cap). Never
    raises: errors are reported in the result so one bad episode cannot
    kill the run."""
    try:
        with EngineWorker(map_dir=str(MAP_DIR)) as engine:
            behaviors = ["production"] if policy == "production" else ["external"]
            engine.start(
                nations=1,
                difficulty="hard",
                map_size="full",
                spawn=list(SPAWN),
                tribes=tribes,
                game_id=seed,
                nation_behaviors=behaviors,
            )
            obs = engine.nation_observe(0)
            me_name = str(obs["me"]["name"])
            orders = 0
            annex_pokes = 0
            winner = obs["winner"]
            tick = int(obs["tick"])
            while winner is None and tick < MAX_TICKS:
                if policy == "farm-p4" and bool(obs["me"]["alive"]):
                    orders, annex_pokes = _farm_tick(engine, obs, orders, annex_pokes)
                state = engine.advance(FARM_CADENCE)
                tick = int(state["tick"])
                winner = state.get("winner")
                obs = engine.nation_observe(0)
                if not bool(obs["me"]["alive"]):
                    break  # dead farmers cannot win; record the loss
            final = engine.nation_observe(0)
            tribes_dead = sum(1 for t in final["tribes"] if not t["alive"])
            return {
                "seed": seed,
                "tribes": tribes,
                "policy": policy,
                "winner": winner,
                "agent_won": winner == me_name,
                "ticks": tick,
                "orders": orders,
                "annex_pokes": annex_pokes,
                "tribes_dead": tribes_dead,
                "tiles": int(final["me"]["tiles"]),
            }
    except Exception as exc:  # noqa: BLE001 — run must survive bad episodes
        logger.exception("episode failed: %s/%s", seed, policy)
        return {
            "seed": seed,
            "tribes": tribes,
            "policy": policy,
            "error": str(exc),
        }


def _farm_tick(
    engine: EngineWorker, obs: dict[str, Any], orders: int, annex_pokes: int
) -> tuple[int, int]:
    """One farm-p4 decision: enclosed tribes get a token poke, then up to
    FARM_PARALLEL density-ordered fronts take min(4x target, budget),
    skipping fronts below 2x target (production's exact rules). Returns
    updated (orders, annex_pokes)."""
    troops = float(obs["me"]["troops"])
    cap = float(obs["me"]["maxTroops"])
    if troops <= 0:
        return orders, annex_pokes
    # Retain floor (troopSendCap): keep 75% of the strongest observed other
    # nation; bot/human neighbors are exempt, approximated here by nations.
    retain = 0.0
    for other in obs["others"]:
        if bool(other["alive"]):
            retain = max(retain, FARM_RETAIN * float(other["troops"]))
    budget = min(troops - FARM_RESERVE * cap, troops - retain)
    fired = 0
    # Edge 2: enclosed tribes first — a token poke triggers cluster
    # deletion plus the <100-tile flip at near-zero cost.
    for tribe in _bordering(obs):
        if fired >= FARM_PARALLEL:
            break
        if not bool(tribe["enclosed"]):
            continue
        engine.nation_order(0, str(tribe["id"]), troops * ANNEX_SHARE)
        orders += 1
        annex_pokes += 1
        budget -= troops * ANNEX_SHARE
        fired += 1
    # Parity floor: density ascending (production's attackBots sort).
    for tribe in sorted(_bordering(obs), key=_density):
        if fired >= FARM_PARALLEL:
            break
        if bool(tribe["enclosed"]):
            continue  # already poked above
        target_troops = float(tribe["troops"])
        send = min(FARM_FORCE_MULT * target_troops, budget)
        if send < FARM_SKIP_MULT * target_troops or send < 1:
            continue
        engine.nation_order(0, str(tribe["id"]), send)
        orders += 1
        budget -= send
        fired += 1
    return orders, annex_pokes


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
    parser.add_argument("--tribes", type=int, default=20)
    parser.add_argument(
        "--policies",
        default="expand,production,farm-p4",
        help="comma-separated policies (default: %(default)s)",
    )
    parser.add_argument("--jobs", type=int, default=6)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent / "results" / "sweep_tribes.json",
    )
    args = parser.parse_args(argv)
    seeds = [s for s in args.seeds.split(",") if s]
    policies = [p for p in args.policies.split(",") if p]
    specs = [(s, int(args.tribes), p) for s in seeds for p in policies]
    results: list[dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(run_episode, s, tribes, p) for (s, tribes, p) in specs]
        for spec, future in zip(specs, futures):
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
