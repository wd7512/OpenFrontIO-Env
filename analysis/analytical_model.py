"""Analytical model of solo expansion on The Box (phase 1) plus the
tribe-farming kill model (phase 2).

Derives the game from the exact engine equations (no game grid search),
verifies each equation against measured engine behaviour, then solves for
the optimal policies.

Engine sources (vendor/OpenFrontIO, pinned engine):
- troop regen / max troops:  core/configuration/Config.ts
  ``troopIncreaseRate`` / ``maxTroops`` (human branch)
- expansion cost + speed:    core/configuration/Config.ts ``attackLogic``
  (TerraNullius branch) + ``attackTilesPerTick`` (TerraNullius branch)
- per-tick conquest loop:    core/execution/AttackExecution.ts ``tick``
- win rule:                  core/execution/WinCheckExecution.ts
  (FFA: tile share > ``percentageTilesOwnedToWin`` = 80%)
- player-vs-player combat:   core/configuration/Config.ts ``attackLogic``
  (player branch) + ``attackTilesPerTick`` (player branch)
- production bot farming:    core/execution/utils/AiAttackBehavior.ts
  ``attackBots`` / ``calculateBotAttackTroops`` / ``isAttackTooWeak`` /
  ``troopSendCap`` + core/execution/NationExecution.ts ratios/cadence
- instant flip + annex:      core/execution/AttackExecution.ts
  ``handleDeadDefender`` (<100 tiles -> conquerPlayer) +
  core/execution/PlayerExecution.ts ``removeClusters`` (surrounded
  clusters deleted; largest cluster deleted when surrounded by a single
  non-friendly player)

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

# ---------------------------------------------------------------------------
# Phase-1 maxed agent (analysis/maxed_agents.md): the derived opening composed
# with the 1-tick race optimum. Opening = (threshold, ratio, interval) through
# OPENING_UNTIL; race = the same afterward.
# ---------------------------------------------------------------------------
OPENING_UNTIL = 260
PHASE1_OPENING = (0.20, 0.15, 21)
PHASE1_RACE = (0.36, 0.005, 1)

# Frontier coefficient: attack budget per tick is 2 * (borderSize + U{0..4}),
# borderSize ~= BORDER_K * sqrt(tiles). Calibrated from three fixed-attack
# probes (see docstring / report): measured k = 3.83 / 3.84 / 3.86.
BORDER_K = 3.845


# ---------------------------------------------------------------------------
# Exact engine equations
# ---------------------------------------------------------------------------
# Nation economies (Config.ts startManpower / maxTroops / troopIncreaseRate,
# Nation branch): (start_troops, max_mult, regen_mult). Human = Hard.
NATION_ECONOMY = {
    "easy": (12500.0, 0.5, 0.9),
    "medium": (18750.0, 0.75, 0.95),
    "hard": (25000.0, 1.0, 1.0),
    "impossible": (31250.0, 1.25, 1.05),
    # Improved-hard is a new difficulty with Hard economy (worker.ts maps it
    # to Difficulty.Hard) and custom threshold-ratio behavior.
    "improved-hard": (25000.0, 1.0, 1.0),
}


def max_troops(tiles: float, max_mult: float = 1.0) -> float:
    """Config.maxTroops (no cities built in these runs).

    Human branch at max_mult=1.0; nation economies scale the cap
    (0.5/0.75/1.0/1.25 for easy/medium/hard/impossible).
    """
    return 2 * (tiles**0.6 * 1000 + 50000) * max_mult


def regen(
    troops: float, tiles: float, max_mult: float = 1.0, regen_mult: float = 1.0
) -> float:
    """Config.troopIncreaseRate. regen_mult is the nation difficulty factor
    (0.9/0.95/1.0/1.05); the cap inside the (1 - troops/cap) term already
    carries max_mult, matching the engine order (cap first, then factor)."""
    cap = max_troops(tiles, max_mult)
    return (10 + troops**0.73 / 4) * (1 - troops / cap) * regen_mult


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
    threshold: float,
    ratio: float,
    max_ticks: int = 200000,
    interval: int = 1,
    max_mult: float = 1.0,
    regen_mult: float = 1.0,
    start_troops: float = SPAWN_TROOPS,
) -> dict[str, float]:
    """Run the mean-field model. Returns crossing tick of the 80% win line.

    ``interval`` is the decision cadence in ticks (1 = every tick,
    50 = every 5s); the attack itself still conquers every tick.
    ``max_mult``/``regen_mult``/``start_troops`` select the economy
    (defaults = human; see NATION_ECONOMY for nation values).

    The loop mirrors the game sweep exactly: the engine starts at tick 2
    with a fresh spawn, and ``sweep_single_entity.run_agent`` sends when
    ``(tick - 2) % interval == 0``, so the model uses the same schedule —
    first send decided at tick 2 for every cadence.
    """
    tiles = float(SPAWN_TILES)
    troops = float(start_troops)
    attack = 0.0
    pending = 0.0  # ordered troops join the attack next tick (intent delay)
    target = WIN_SHARE * TOTAL_LAND
    for tick in range(FIRST_DECISION_TICK, max_ticks + 1):
        attack += pending
        pending = 0.0
        cap = max_troops(tiles, max_mult)
        if (tick - FIRST_DECISION_TICK) % interval == 0 and troops >= threshold * cap:
            send = min(troops, ratio * troops)
            troops -= send
            pending = send
        gained, attack = conquest_tiles(attack, budget(tiles))
        if attack < 1:
            attack = 0.0
        tiles += gained
        troops += regen(troops, tiles, max_mult, regen_mult)
        if tiles > target:
            return {"crossing_tick": float(tick), "tiles": tiles, "troops": troops}
    return {"crossing_tick": float("inf"), "tiles": tiles, "troops": troops}


# ---------------------------------------------------------------------------
# Opening sub-benchmark: does a Hard-style Tick-1 burst help the race?
# ---------------------------------------------------------------------------
def simulate_opening(
    threshold: float,
    ratio: float,
    interval: int = 52,
    burst_ratio: float = 0.0,
    horizon: int = 260,
    max_ticks: int = 200000,
    max_mult: float = 1.0,
    regen_mult: float = 1.0,
    start_troops: float = SPAWN_TROOPS,
) -> dict[str, float]:
    """Same dynamics as ``simulate`` plus a one-shot opening burst.

    On the first decision tick a burst policy sends ``burst_ratio * troops``
    (Hard's Tick-1 80-90% throw) *instead of* the rhythm send, then resumes
    the gated rhythm on its normal schedule. Reports both the 80% crossing
    tick and tiles owned at ``horizon`` so the opening metric and the race
    metric can be read side by side. A burst parks troops in the front,
    where they earn no regen (governing eq. 6), so this settles whether the
    early land is free or borrowed from the race.
    """
    tiles = float(SPAWN_TILES)
    troops = float(start_troops)
    attack = 0.0
    pending = 0.0
    target = WIN_SHARE * TOTAL_LAND
    tiles_at_horizon = float("nan")
    for tick in range(FIRST_DECISION_TICK, max_ticks + 1):
        attack += pending
        pending = 0.0
        cap = max_troops(tiles, max_mult)
        if tick == FIRST_DECISION_TICK and burst_ratio > 0:
            send = min(troops, burst_ratio * troops)
            troops -= send
            pending = send
        elif (tick - FIRST_DECISION_TICK) % interval == 0 and troops >= (
            threshold * cap
        ):
            send = min(troops, ratio * troops)
            troops -= send
            pending = send
        gained, attack = conquest_tiles(attack, budget(tiles))
        if attack < 1:
            attack = 0.0
        tiles += gained
        troops += regen(troops, tiles, max_mult, regen_mult)
        if tick == horizon:
            tiles_at_horizon = tiles
        if tiles > target:
            return {
                "crossing_tick": float(tick),
                "tiles_at_horizon": tiles_at_horizon,
                "tiles": tiles,
                "troops": troops,
            }
    return {
        "crossing_tick": float("inf"),
        "tiles_at_horizon": tiles_at_horizon,
        "tiles": tiles,
        "troops": troops,
    }


def find_opening_optimum(interval: int = 52, horizon: int = 260) -> dict[str, float]:
    """argmax over burst_ratio of tiles at ``horizon`` (the opening metric).

    Sweeps burst_ratio on a grid (the objective is monotone-ish and cheap);
    the race crossing tick is reported alongside to show the trade.
    """
    best = (0.0, 0.0, 0.0)  # burst, tiles, crossing
    for i in range(0, 101):
        burst = i / 100.0
        out = simulate_opening(
            0.38, 0.15, interval=interval, burst_ratio=burst, horizon=horizon
        )
        if out["tiles_at_horizon"] > best[1]:
            best = (burst, out["tiles_at_horizon"], out["crossing_tick"])
    return {
        "burst_ratio": best[0],
        "tiles_at_horizon": best[1],
        "crossing_tick": best[2],
    }


def simulate_graft(
    opening: tuple[float, float, int] = (0.20, 0.30, 13),
    race: tuple[float, float, int] = (0.38, 0.15, 52),
    until: int = 260,
    horizon: int = 260,
    max_ticks: int = 200000,
    max_mult: float = 1.0,
    regen_mult: float = 1.0,
    start_troops: float = SPAWN_TROOPS,
) -> dict[str, float]:
    """Composed phase-1 policy: an aggressive opening, then the phase-1 race
    rhythm. ``opening`` = (threshold, ratio, interval) used through tick
    ``until``; ``race`` = the same for later ticks. Reports tiles at
    ``horizon`` (opening metric) and the 80% crossing tick (race metric).

    This is the phase-1a optimum composed onto phase 1b: the ungated
    short-cadence opening reaches production-Hard parity where the race
    rhythm cedes 60 ticks to its gate, and the reversion keeps the race
    crossing at the phase-1 optimum (model: 5,172 tiles @260 / 7,822).
    """
    o_th, o_ratio, o_int = opening
    r_th, r_ratio, r_int = race
    tiles = float(SPAWN_TILES)
    troops = float(start_troops)
    attack = 0.0
    pending = 0.0
    target = WIN_SHARE * TOTAL_LAND
    tiles_at_horizon = float("nan")
    for tick in range(FIRST_DECISION_TICK, max_ticks + 1):
        attack += pending
        pending = 0.0
        cap = max_troops(tiles, max_mult)
        if tick <= until:
            th, ratio, interval = o_th, o_ratio, o_int
        else:
            th, ratio, interval = r_th, r_ratio, r_int
        if (tick - FIRST_DECISION_TICK) % interval == 0 and troops >= (th * cap):
            send = min(troops, ratio * troops)
            troops -= send
            pending = send
        gained, attack = conquest_tiles(attack, budget(tiles))
        if attack < 1:
            attack = 0.0
        tiles += gained
        troops += regen(troops, tiles, max_mult, regen_mult)
        if tick == horizon:
            tiles_at_horizon = tiles
        if tiles > target:
            return {
                "crossing_tick": float(tick),
                "tiles_at_horizon": tiles_at_horizon,
                "tiles": tiles,
                "troops": troops,
            }
    return {
        "crossing_tick": float("inf"),
        "tiles_at_horizon": tiles_at_horizon,
        "tiles": tiles,
        "troops": troops,
    }


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
    interval: int = 1,
    starts: tuple[tuple[float, float], ...] | None = None,
    max_mult: float = 1.0,
    regen_mult: float = 1.0,
    start_troops: float = SPAWN_TROOPS,
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
        return (
            simulate(
                thc,
                rac,
                interval=interval,
                max_mult=max_mult,
                regen_mult=regen_mult,
                start_troops=start_troops,
            )["crossing_tick"]
            + 1e9 * penalty
        )

    best = (0.0, 0.0, float("inf"))
    for start in DEFAULT_STARTS if starts is None else starts:
        th, ra, val = _nelder_mead(objective, start)
        if val < best[2]:
            best = (th, ra, val)
    return {"threshold": best[0], "ratio": best[1], "crossing_tick": best[2]}


# ---------------------------------------------------------------------------
# Phase 2: tribe-farming kill model (nation vs bot, Box plains)
# ---------------------------------------------------------------------------
# Player-branch combat (Config.attackLogic, Plains, no defense posts, no
# fallout; nation-vs-bot mag discount 0.7 -> MAG_PVP = 56). Debuff factors
# (large-defender sigmoid, large-attacker bonus) default to 1.0 = upper
# bound on cost; both equal 1.0 below 100k attacker tiles on the Box.
MAG_PVP = MAG_PLAINS * 0.7  # 56.0
# Production bot-farming constants (AiAttackBehavior / NationExecution):
FARM_FORCE_MULT = 4.0  # tranche = 4x target troops (calculateBotAttackTroops)
FARM_SKIP_MULT = 2.0  # skip front if budget < 2x target
FARM_RESERVE = 0.35  # spend at most troops - 0.35 * cap (reserveRatio 0.30-0.40)
FARM_PARALLEL = 3  # Hard bot-attack parallelism (getBotAttackMaxParallelism)
FARM_CADENCE = 52  # Hard attack loop 45-60 ticks; phase-1 decision step
FARM_RETAIN = 0.75  # keep >= 75% of strongest non-bot neighbor (troopSendCap)
FLIP_TILES = 100.0  # <100 tiles -> instant full conquest (handleDeadDefender)
# Bot economy (startManpower / maxTroops / troopIncreaseRate, Bot branch):
BOT_START_TROOPS = 10000.0
BOT_MAX_MULT = 1.0 / 3.0
BOT_REGEN_MULT = 0.5


def _within(x: float, lo: float, hi: float) -> float:
    return min(hi, max(lo, x))


def pvp_tiles_per_tick(
    attack_troops: float, defender_troops: float, border: float
) -> float:
    """Config.attackTilesPerTick, player branch: pacing budget per game tick."""
    if defender_troops <= 0:
        return 0.5 * border * 3.0
    ratio = attack_troops / defender_troops
    return _within(10.0 * ratio, 0.01, 0.5) * border * 3.0


def pvp_cost_per_tile(
    attack_troops: float, defender_troops: float, debuff: float = 1.0
) -> float:
    """Config.attackLogic tilesPerTickUsed, player branch, Box plains."""
    if defender_troops <= 0 or attack_troops <= 0:
        return SPEED_PLAINS * debuff
    ratio = attack_troops / defender_troops
    return _within(1.0 / (5.0 * ratio), 0.2, 1.5) * SPEED_PLAINS * debuff


def pvp_attacker_loss_per_tile(
    attack_troops: float,
    defender_troops: float,
    density: float,
    debuff: float = 1.0,
) -> float:
    """Config.attackLogic attackerTroopLoss, player branch, Box plains,
    nation-vs-bot: 0.6 * within(D/A, 0.6, 2) * MAG_PVP * 0.8 * debuff
    + 0.4 * 1.3 * density * (MAG_PVP / 100)."""
    if attack_troops <= 0:
        return float("inf")
    ratio = defender_troops / attack_troops
    current = _within(ratio, 0.6, 2.0) * MAG_PVP * 0.8 * debuff
    alt = 1.3 * density * (MAG_PVP / 100.0)
    return 0.6 * current + 0.4 * alt


def siege_tiles_per_tick(
    attack_troops: float,
    defender_troops: float,
    border: float,
    debuff: float = 1.0,
) -> float:
    """Conquered tiles per game tick: pacing budget divided by per-tile cost."""
    pacing = pvp_tiles_per_tick(attack_troops, defender_troops, border)
    cost = pvp_cost_per_tile(attack_troops, defender_troops, debuff)
    return pacing / cost if cost > 0 else 0.0


def siege_ticks(
    tribe_tiles: float,
    attack_troops: float,
    defender_troops: float,
    border: float,
    debuff: float = 1.0,
) -> float:
    """Ticks to shrink a tribe to the <100-tile instant-flip line."""
    rate = siege_tiles_per_tick(attack_troops, defender_troops, border, debuff)
    if rate <= 0:
        return float("inf")
    return max(0.0, tribe_tiles - FLIP_TILES) / rate


def bot_regen(troops: float, tiles: float) -> float:
    """Tribe troop regen per tick (half rate, one-third cap)."""
    cap = max_troops(tiles) * BOT_MAX_MULT
    if troops >= cap:
        return 0.0
    return (10 + troops**0.73 / 4) * (1 - troops / cap) * BOT_REGEN_MULT


def kill_completes(
    attack_troops: float,
    defender_troops: float,
    tribe_tiles: float,
    border: float,
) -> bool:
    """A siege finishes iff defender-pool damage outruns defender regen;
    otherwise it stalls forever and the sent troops are wasted. Damage per
    tick = density * conquered tiles per tick."""
    if tribe_tiles <= 0:
        return False
    density = defender_troops / tribe_tiles
    damage = density * siege_tiles_per_tick(attack_troops, defender_troops, border)
    return damage > bot_regen(defender_troops, tribe_tiles)


def farm_tranches(
    my_troops: float,
    my_cap: float,
    targets: list[tuple[str, float]],
    reserve: float = FARM_RESERVE,
    retain: float = 0.0,
    parallel: int = FARM_PARALLEL,
) -> list[tuple[str, float]]:
    """Production calculateBotAttackTroops per front (density order assumed
    upstream): send min(4x target, budget), skip fronts below 2x target.
    ``targets`` are (label, troops) in attack order; ``retain`` is the
    75%-of-strongest-nation-neighbor floor (0 in a pure race)."""
    budget = min(my_troops - reserve * my_cap, my_troops - retain)
    sends: list[tuple[str, float]] = []
    for label, target_troops in targets[:parallel]:
        send = min(FARM_FORCE_MULT * target_troops, budget)
        if send < FARM_SKIP_MULT * target_troops or send < 1:
            continue
        sends.append((label, send))
        budget -= send
    return sends


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
    logger.info(
        "farm-p4 check: siege(10000 tiles, A=40000 vs D=10000, front=300) "
        "= %.0f ticks; kill completes: %s",
        siege_ticks(10000.0, 40000.0, 10000.0, 300.0),
        kill_completes(40000.0, 10000.0, 10000.0, 300.0),
    )


if __name__ == "__main__":
    main()
