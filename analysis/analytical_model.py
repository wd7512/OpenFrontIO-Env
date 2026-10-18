"""Analytical model of solo expansion on The Box.

Derives the game from the exact engine equations (no game grid search),
verifies each equation against measured engine behaviour, then solves for
the optimal (threshold, ratio) expansion policy.

Engine sources (vendor/OpenFrontIO, pinned engine):
- troop regen / max troops:  core/configuration/Config.ts
  ``troopIncreaseRate`` / ``maxTroops`` (human branch)
- expansion cost + speed:    core/configuration/Config.ts ``attackLogic``
  (TerraNullius branch) + ``attackTilesPerTick`` (TerraNullius branch)
- per-tick conquest loop:    core/execution/AttackExecution.ts ``tick``
- win rule:                  core/execution/WinCheckExecution.ts
  (FFA: tile share > ``percentageTilesOwnedToWin`` = 80%)

The Box is uniformly Plains (map.bin is a single repeated byte 0x82:
land bit set, magnitude 2 < 10 -> Plains, GameMap.ts ``terrainType``),
so mag = 80, speed = 16.5 everywhere.
"""

import logging
import math

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Engine constants
# ---------------------------------------------------------------------------
MAG_PLAINS = 80
SPEED_PLAINS = 16.5
COST_PER_TILE = MAG_PLAINS / 5  # 16 troops per tile (humans vs TerraNullius)
BUDGET_NUMER = 2000 * SPEED_PLAINS  # 33000.0
TOTAL_LAND = 4194304
WIN_SHARE = 0.80
SPAWN_TILES = 52
SPAWN_TROOPS = 25000.0
# Engine starts at tick 2 with a fresh spawn; both the game sweep and this
# model decide sends on ticks with (tick - FIRST_DECISION_TICK) % interval == 0.
FIRST_DECISION_TICK = 2

# Frontier coefficient: attack budget per tick is 2 * (borderSize + U{0..4}),
# borderSize ~= BORDER_K * sqrt(tiles). Calibrated from three fixed-attack
# probes (see docstring / report): measured k = 3.83 / 3.84 / 3.86.
BORDER_K = 3.845


# ---------------------------------------------------------------------------
# Exact engine equations
# ---------------------------------------------------------------------------
def max_troops(tiles: float) -> float:
    """Config.maxTroops, human branch (no cities built in these runs)."""
    return 2 * (tiles**0.6 * 1000 + 50000)


def regen(troops: float, tiles: float) -> float:
    """Config.troopIncreaseRate, human branch."""
    cap = max_troops(tiles)
    return (10 + troops**0.73 / 4) * (1 - troops / cap)


def tile_budget_cost(attack_troops: float) -> float:
    """Config.attackLogic, TerraNullius branch (plains)."""
    return min(100, max(5, BUDGET_NUMER / attack_troops))


def budget(tiles: float) -> float:
    """Mean per-tick conquest budget (E[U{0..4}] = 2)."""
    return 2 * (BORDER_K * math.sqrt(tiles) + 2)


# ---------------------------------------------------------------------------
# Per-tick conquest, closed form
# ---------------------------------------------------------------------------
def conquest_tiles(attack_troops: float, tick_budget: float) -> tuple[int, float]:
    """Reproduce AttackExecution.tick vs TerraNullius for one game tick.

    Loop semantics: while budget > 0: stop if troops < 1; conquer one tile,
    budget -= within(33000/troops, 5, 100), troops -= 16. Returns
    (tiles_conquered, troops_remaining);Caller maps < 1 troop to a dead attack.
    """
    if attack_troops < 1 or tick_budget <= 0:
        return 0, attack_troops
    n = 0
    w = attack_troops
    b = float(tick_budget)

    # Region A: flat cost 5 while w >= 6600.
    if w >= 6600:
        room = int((w - 6600) // 16) + 1
        take = min(room, int(math.ceil(b / 5)))
        n += take
        w -= 16 * take
        b -= 5 * take
        if b <= 0:
            return n, max(0.0, w)

    # Region B: cost 33000/w while 330 < w < 6600 (integral + exact top-up).
    if w > 330 and b > 0 and w >= 1:
        w_end = max(330.0, w * math.exp(-16.0 * b / BUDGET_NUMER))
        take = int((w - w_end) // 16)
        if take > 0:
            w_after = w - 16 * take
            b -= (BUDGET_NUMER / 16) * math.log(w / w_after)
            w = w_after
            n += take
        guard = 0
        while w > 330 and w >= 1 and b >= BUDGET_NUMER / w and guard < 8:
            b -= BUDGET_NUMER / w
            w -= 16
            n += 1
            guard += 1

    # Region C: flat cost 100 while w <= 330 (needs w >= 1 per tile).
    if b > 0 and w >= 1:
        room = int((w - 1) // 16) + 1
        take = min(room, int(math.ceil(b / 100)))
        n += take
        w -= 16 * take
        b -= 100 * take

    return n, max(0.0, w)


# ---------------------------------------------------------------------------
# Policy simulator: 1-tick (threshold, ratio) expansion, no units
# ---------------------------------------------------------------------------
def simulate(
    threshold: float, ratio: float, max_ticks: int = 200000, interval: int = 1
) -> dict[str, float]:
    """Run the mean-field model. Returns crossing tick of the 80% win line.

    ``interval`` is the decision cadence in ticks (1 = every tick,
    50 = every 5s); the attack itself still conquers every tick.

    The loop mirrors the game sweep exactly: the engine starts at tick 2
    with a fresh spawn, and ``sweep_single_entity.run_agent`` sends when
    ``(tick - 2) % interval == 0``, so the model uses the same schedule —
    first send decided at tick 2 for every cadence.
    """
    tiles = float(SPAWN_TILES)
    troops = float(SPAWN_TROOPS)
    attack = 0.0
    pending = 0.0  # ordered troops join the attack next tick (intent delay)
    target = WIN_SHARE * TOTAL_LAND
    for tick in range(FIRST_DECISION_TICK, max_ticks + 1):
        attack += pending
        pending = 0.0
        cap = max_troops(tiles)
        if (tick - FIRST_DECISION_TICK) % interval == 0 and troops >= threshold * cap:
            send = min(troops, ratio * troops)
            troops -= send
            pending = send
        gained, attack = conquest_tiles(attack, budget(tiles))
        if attack < 1:
            attack = 0.0
        tiles += gained
        troops += regen(troops, tiles)
        if tiles > target:
            return {"crossing_tick": float(tick), "tiles": tiles, "troops": troops}
    return {"crossing_tick": float("inf"), "tiles": tiles, "troops": troops}


# ---------------------------------------------------------------------------
# Analytic optimum for the threshold: argmax of the regen rate
# ---------------------------------------------------------------------------
def optimal_threshold_theory(cap: float) -> float:
    """Fraction u = troops/cap maximizing (10 + (u*cap)^0.73/4) * (1-u).

    Ignoring the +10: 0.73*(1-u)/u = 1 -> u* = 0.73/1.73 ~= 0.422.
    Solved here exactly (bisection) including the +10 term.
    """

    def f(u: float) -> float:
        return (10 + (u * cap) ** 0.73 / 4) * (1 - u)

    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        h = 1e-7
        if (f(mid + h) - f(mid - h)) / (2 * h) > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


# ---------------------------------------------------------------------------
# Tiny Nelder-Mead (stdlib only) for the 2-parameter model optimum
# ---------------------------------------------------------------------------
def _nelder_mead(
    fn, start: tuple[float, float], step=(0.05, 0.02), iters: int = 200
) -> tuple[float, float, float]:
    alpha, gamma, rho, sigma = 1.0, 2.0, 0.5, 0.5
    x0 = list(start)
    simplex = [x0, [x0[0] + step[0], x0[1]], [x0[0], x0[1] + step[1]]]
    vals = [fn(p) for p in simplex]
    for _ in range(iters):
        order = sorted(range(3), key=lambda i: vals[i])
        simplex = [simplex[i] for i in order]
        vals = [vals[i] for i in order]
        centroid = [
            (simplex[0][0] + simplex[1][0]) / 2,
            (simplex[0][1] + simplex[1][1]) / 2,
        ]
        xr = [
            centroid[0] + alpha * (centroid[0] - simplex[2][0]),
            centroid[1] + alpha * (centroid[1] - simplex[2][1]),
        ]
        fr = fn(xr)
        if vals[0] <= fr < vals[1]:
            simplex[2], vals[2] = xr, fr
            continue
        if fr < vals[0]:
            xe = [
                centroid[0] + gamma * (xr[0] - centroid[0]),
                centroid[1] + gamma * (xr[1] - centroid[1]),
            ]
            fe = fn(xe)
            simplex[2], vals[2] = (xe, fe) if fe < fr else (xr, fr)
            continue
        xc = [
            centroid[0] + rho * (simplex[2][0] - centroid[0]),
            centroid[1] + rho * (simplex[2][1] - centroid[1]),
        ]
        fc = fn(xc)
        if fc < vals[2]:
            simplex[2], vals[2] = xc, fc
            continue
        for i in (1, 2):
            simplex[i] = [
                simplex[0][0] + sigma * (simplex[i][0] - simplex[0][0]),
                simplex[0][1] + sigma * (simplex[i][1] - simplex[0][1]),
            ]
            vals[i] = fn(simplex[i])
    best = min(range(3), key=lambda i: vals[i])
    return simplex[best][0], simplex[best][1], vals[best]


DEFAULT_STARTS = (
    (0.4, 0.10),
    (0.2, 0.10),
    (0.6, 0.10),
    (0.4, 0.30),
    (0.1, 0.05),
    (0.7, 0.50),
    (0.0, 0.10),
    (0.42, 0.05),
)


def find_optimum(
    interval: int = 1, starts: tuple[tuple[float, float], ...] | None = None
) -> dict[str, float]:
    """Global optimum of crossing_tick over (threshold, ratio) in the model."""

    def objective(p: list[float]) -> float:
        th, ra = p[0], p[1]
        penalty = (
            min(0.0, th) ** 2
            + max(0.0, th - 0.95) ** 2
            + min(0.0, ra - 0.001) ** 2
            + max(0.0, ra - 1.0) ** 2
        )
        thc = min(0.95, max(0.0, th))
        rac = min(1.0, max(0.001, ra))
        return simulate(thc, rac, interval=interval)["crossing_tick"] + 1e9 * penalty

    best = (0.0, 0.0, float("inf"))
    for start in DEFAULT_STARTS if starts is None else starts:
        th, ra, val = _nelder_mead(objective, start)
        if val < best[2]:
            best = (th, ra, val)
    return {"threshold": best[0], "ratio": best[1], "crossing_tick": best[2]}


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logger.info(
        "regen-argmax thresholds: cap=1e5 -> %.4f, cap=1e6 -> %.4f, cap=1e7 -> %.4f",
        optimal_threshold_theory(1e5),
        optimal_threshold_theory(1e6),
        optimal_threshold_theory(1e7),
    )
    base = simulate(0.40, 0.10)
    logger.info("model at (0.40, 0.10): crossing tick %.0f", base["crossing_tick"])
    opt = find_optimum()
    logger.info(
        "model optimum: threshold=%.4f ratio=%.4f crossing=%.0f",
        opt["threshold"],
        opt["ratio"],
        opt["crossing_tick"],
    )
    opt50 = find_optimum(interval=50)
    logger.info(
        "model 50-tick optimum: threshold=%.4f ratio=%.4f crossing=%.0f",
        opt50["threshold"],
        opt50["ratio"],
        opt50["crossing_tick"],
    )


if __name__ == "__main__":
    main()
