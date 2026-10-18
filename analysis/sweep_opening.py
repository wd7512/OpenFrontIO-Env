"""Phase 1a benchmark: the opening sub-scale of solo expansion on The Box.

Phase 1 (expansion) has two scales with different optima, and the original
phase-1 work only benchmarked the second (ticks to win a tribeless race).
On that metric Improved-Hard is optimal, but it cedes the *opening*: its
0.38*cap gate cannot fire until troops reach ~46k, so its first send lands
near tick 60 while production Hard expands from tick 1.

This runner is the missing benchmark. It measures the opening directly —
tiles owned at fixed horizons — for three brains on the same tribeless Box
seeds, and reports each brain's race crossing tick alongside so the
opening-vs-race trade is visible:

  - ``ih``    Improved-Hard human agent: 0.38/0.15/52 (the phase-1 race
              optimum, gated).
  - ``graft`` the time-varying composition derived in analytical_model.py:
              ungated 0.20/0.30 at 13-tick cadence until tick 260, then the
              phase-1 rhythm. Opening optimum composed onto the race
              optimum.
  - ``hard``  production Hard nation (human idle) — the bar.

Derivation: ``analytical_model.simulate_opening`` / ``find_opening_optimum``.
Model prediction for the graft: tiles@260 ~= 5,172, crossing ~= 7,822.

Usage:
  uv run python analysis/sweep_opening.py --jobs 6
  uv run python analysis/sweep_opening.py --seeds BOX-OPEN-A --policies ih,graft
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
    FIRST_DECISION_TICK,
    OPENING_UNTIL,
    PHASE1_OPENING,
    PHASE1_RACE,
    TOTAL_LAND,
    WIN_SHARE,
    max_troops,
)

logger = logging.getLogger(__name__)

DEFAULT_SEEDS = [f"BOX-OPEN-{c}" for c in "ABCDEF"]
CHECKPOINTS = (60, 130, 260, 520)
MAX_TICKS = 300000
GRAFT_UNTIL = 260  # tick through which the opening phase is aggressive
# Opening-phase (threshold, ratio, interval) and the phase-1 race rhythm.
OPENING_PHASE = (0.20, 0.30, 13)
RACE_PHASE = (0.38, 0.15, 52)
# A policy is a piecewise list of (until_tick, threshold, ratio, interval);
# the last segment's ``until`` is a large sentinel (takes over for good).
POLICIES: dict[str, list[tuple[int, float, float, int]]] = {
    "ih": [(MAX_TICKS, *RACE_PHASE)],
    "graft": [(GRAFT_UNTIL, *OPENING_PHASE), (MAX_TICKS, *RACE_PHASE)],
    "p1max": [(OPENING_UNTIL, *PHASE1_OPENING), (MAX_TICKS, *PHASE1_RACE)],
}


def _send(tick: int, tiles: float, troops: float, policy: str) -> float | None:
    """Troops to send this tick for a human-agent policy (None = hold)."""
    cap = max_troops(max(tiles, 1))
    th, ratio, interval = POLICIES[policy][-1][1:]
    for until, sth, sratio, sinterval in POLICIES[policy]:
        if tick <= until:
            th, ratio, interval = sth, sratio, sinterval
            break
    if (tick - FIRST_DECISION_TICK) % interval == 0 and troops >= th * cap:
        return troops * ratio
    return None


def run_episode(seed: str, policy: str) -> dict[str, Any]:
    """One opening episode. Never raises: errors land in the result."""
    try:
        with EngineWorker(map_dir=str(MAP_DIR)) as engine:
            if policy == "hard":
                return _run_hard_nation(engine, seed)
            return _run_human_agent(engine, seed, policy)
    except Exception as exc:  # noqa: BLE001 — one bad episode must not kill the run
        logger.exception("episode failed: %s/%s", seed, policy)
        return {"seed": seed, "policy": policy, "error": str(exc)}


def _run_human_agent(engine: EngineWorker, seed: str, policy: str) -> dict[str, Any]:
    state = engine.start(
        nations=0, tribes=0, spawn=list(SPAWN), map_size="full", game_id=seed
    )
    tick = int(state["tick"])
    tiles = int(state["human"]["tiles"])
    me_name = str(state["human"]["name"])
    winner = None
    crossing: int | None = None
    checkpoints: dict[int, int] = {}
    while winner is None and tick < MAX_TICKS:
        send = _send(tick, float(tiles), float(state["human"]["troops"]), policy)
        if send is not None and send >= 1:
            try:
                engine.attack(target="expand", troops=send)
            except Exception:  # noqa: BLE001 — a refused order is a no-op
                pass
        state = engine.advance(1)
        tick = int(state["tick"])
        tiles = int(state["human"]["tiles"])
        if tick in CHECKPOINTS:
            checkpoints[tick] = tiles
        if crossing is None and tiles > WIN_SHARE * TOTAL_LAND:
            crossing = tick
        winner = state.get("winner")
    return {
        "seed": seed,
        "policy": policy,
        "winner": winner,
        "agent_won": winner == me_name,
        "crossing_tick": crossing,
        "tiles_at": {str(k): v for k, v in checkpoints.items()},
        "final_tiles": tiles,
    }


def _run_hard_nation(engine: EngineWorker, seed: str) -> dict[str, Any]:
    engine.start(
        nations=1,
        difficulty="hard",
        map_size="full",
        spawn=list(SPAWN),
        tribes=0,
        game_id=seed,
    )
    obs = engine.nation_observe(0)
    tick = int(obs["tick"])
    winner = obs["winner"]
    checkpoints: dict[int, int] = {}
    while winner is None and tick < MAX_TICKS:
        if tick in CHECKPOINTS:
            checkpoints[tick] = int(obs["me"]["tiles"])
        state = engine.advance(1)
        tick = int(state["tick"])
        winner = state.get("winner")
        obs = engine.nation_observe(0)
    if tick in CHECKPOINTS:
        checkpoints[tick] = int(obs["me"]["tiles"])
    return {
        "seed": seed,
        "policy": "hard",
        "winner": winner,
        "tiles_at": {str(k): v for k, v in checkpoints.items()},
        "final_tiles": int(obs["me"]["tiles"]),
    }


def _task(spec: tuple[str, str]) -> dict[str, Any]:
    seed, policy = spec
    return run_episode(seed, policy)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", default=",".join(DEFAULT_SEEDS))
    parser.add_argument("--policies", default="ih,graft,p1max,hard")
    parser.add_argument("--jobs", type=int, default=6)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent / "results" / "opening_race.json",
    )
    args = parser.parse_args(argv)
    seeds = [s for s in args.seeds.split(",") if s]
    policies = [p for p in args.policies.split(",") if p]
    specs = [(s, p) for s in seeds for p in policies]
    results: list[dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        for result in pool.map(_task, specs):
            results.append(result)
            logger.info(result)
    payload = {
        "created": datetime.now(timezone.utc).isoformat(),
        "checkpoints": list(CHECKPOINTS),
        "episodes": results,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=1))
    print(f"wrote {len(results)} episodes to {args.out}")
    return 0


if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parent.parent)
    sys.exit(main())
