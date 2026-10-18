"""Phase 3a benchmark: 1v1 nation duel on The Box (the fighting skill).

Framework instance (see analysis/framework.md): phase 3's *arena* is the
phase-2 arena plus a rival nation. This runner is the isolated-duel scale
(0 tribes, 1 rival) — the fighting skill alone. ``--tribes N`` gives the
nested contested scale (3b).

One external nation (index 0, the proven expansion autopilot body) vs one
production Hard nation (index 1), idle human third party. Metric: does the
agent win the world. Gate: beat production Hard paired.

Policies (the agent's injected orders; the autopilot keeps expanding on the
same ticks — production alternates TN-or-players per attack tick, we do
both, the phase-2 edge):

  - ``expand``      no orders (Improved-Hard play) — the losing baseline.
  - ``raid``        15% of troops at the enemy every 52 ticks (probe).
  - ``commit``      40% of troops at the enemy every 52 ticks (probe).
  - ``p4``          derived: raid only when the pvp kill model says the
                    siege completes, with a min(4x enemy, budget) tranche,
                    skipping fronts below 2x (farm-p4's rules, retargeted
                    from tribes to the rival nation). Uses nation defender
                    regen (not the bot regen of the farming model).

Usage:
  uv run python analysis/sweep_duel.py --jobs 6
  uv run python analysis/sweep_duel.py --seeds BOX-DUEL-A --policies expand,p4
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
    BORDER_K,
    FARM_CADENCE,
    FARM_FORCE_MULT,
    FARM_RESERVE,
    FARM_RETAIN,
    FARM_SKIP_MULT,
    regen as nation_regen,
    siege_tiles_per_tick,
)

logger = logging.getLogger(__name__)

DEFAULT_SEEDS = [f"BOX-DUEL-{c}" for c in ("G", "H", "I", "J", "K", "L")]
MAX_TICKS = 300000
RAID_SHARE = 0.15
COMMIT_SHARE = 0.40


def _living_others(obs: dict[str, Any]) -> list[dict[str, Any]]:
    return [o for o in obs["others"] if bool(o["alive"])]


def _target_label(agent_index: int, others_index: int) -> str:
    enemy_index = others_index if others_index < agent_index else others_index + 1
    return f"nation-{enemy_index + 1}"


def _kill_completes_nation(
    attack_troops: float, defender_troops: float, tiles: float, border: float
) -> bool:
    """pvp siege finishes iff defender-pool damage outruns nation regen."""
    if tiles <= 0 or attack_troops <= 0:
        return False
    density = defender_troops / tiles
    damage = density * siege_tiles_per_tick(attack_troops, defender_troops, border)
    return damage > nation_regen(defender_troops, tiles)


def _border_estimate(tiles: float) -> float:
    return BORDER_K * max(tiles, 1.0) ** 0.5


def _orders_for(
    policy: str, obs: dict[str, Any], agent_index: int
) -> list[tuple[str, float]]:
    others = _living_others(obs)
    if not others:
        return []
    me = obs["me"]
    if not bool(me["alive"]):
        return []
    troops = float(me["troops"])
    cap = float(me["maxTroops"])
    label = _target_label(agent_index, 0)
    enemy = others[0]
    if policy == "raid":
        return [(label, troops * RAID_SHARE)]
    if policy == "commit":
        return [(label, troops * COMMIT_SHARE)]
    if policy != "p4":
        return []
    enemy_troops = float(enemy["troops"])
    enemy_tiles = float(enemy["tiles"])
    retain = FARM_RETAIN * enemy_troops
    budget = min(troops - FARM_RESERVE * cap, troops - retain)
    send = min(FARM_FORCE_MULT * enemy_troops, budget)
    if send < FARM_SKIP_MULT * enemy_troops or send < 1:
        return []
    if not _kill_completes_nation(
        send, enemy_troops, enemy_tiles, _border_estimate(enemy_tiles)
    ):
        return []
    return [(label, send)]


def run_episode(seed: str, policy: str, tribes: int = 0) -> dict[str, Any]:
    try:
        with EngineWorker(map_dir=str(MAP_DIR)) as engine:
            behaviors = ["production", "production"]
            if policy != "production":
                behaviors[0] = "external"
            engine.start(
                nations=2,
                difficulty="hard",
                map_size="full",
                spawn=list(SPAWN),
                tribes=tribes,
                game_id=seed,
                nation_behaviors=behaviors,
            )
            obs = engine.nation_observe(0)
            me_name = str(obs["me"]["name"])
            winner = obs["winner"]
            tick = int(obs["tick"])
            orders = 0
            while winner is None and tick < MAX_TICKS:
                if policy != "production" and bool(obs["me"]["alive"]):
                    for target, t in _orders_for(policy, obs, 0):
                        if t >= 1:
                            engine.nation_order(0, target, t)
                            orders += 1
                state = engine.advance(FARM_CADENCE)
                tick = int(state["tick"])
                winner = state.get("winner")
                obs = engine.nation_observe(0)
                if not bool(obs["me"]["alive"]):
                    break
            final = engine.nation_observe(0)
            return {
                "seed": seed,
                "policy": policy,
                "tribes": tribes,
                "winner": winner,
                "agent_won": winner == me_name,
                "ticks": tick,
                "orders": orders,
                "final_tiles": int(final["me"]["tiles"]),
            }
    except Exception as exc:  # noqa: BLE001 — one bad episode must not kill the run
        logger.exception("episode failed: %s/%s", seed, policy)
        return {"seed": seed, "policy": policy, "tribes": tribes, "error": str(exc)}


def _task(spec: tuple[str, str, int]) -> dict[str, Any]:
    seed, policy, tribes = spec
    return run_episode(seed, policy, tribes)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", default=",".join(DEFAULT_SEEDS))
    parser.add_argument("--policies", default="production,expand,raid,p4")
    parser.add_argument("--tribes", type=int, default=0)
    parser.add_argument("--jobs", type=int, default=6)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent / "results" / "sweep_duel.json",
    )
    args = parser.parse_args(argv)
    seeds = [s for s in args.seeds.split(",") if s]
    policies = [p for p in args.policies.split(",") if p]
    specs = [(s, p, int(args.tribes)) for s in seeds for p in policies]
    results: list[dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        for result in pool.map(_task, specs):
            results.append(result)
            logger.info(result)
    payload = {
        "created": datetime.now(timezone.utc).isoformat(),
        "tribes": int(args.tribes),
        "episodes": results,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=1))
    print(f"wrote {len(results)} episodes to {args.out}")
    return 0


if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parent.parent)
    sys.exit(main())
