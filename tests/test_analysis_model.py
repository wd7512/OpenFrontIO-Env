"""Regression tests for the Box single-entity analytical model (no engine).

Pins the exact model predictions behind box_single_entity_baseline.md so
any change to the equations, send schedule, or optimizer surfaces here.
All runs take milliseconds (pure stdlib mean-field model).
"""

from __future__ import annotations

from analysis.analytical_model import (
    FIRST_DECISION_TICK,
    NATION_ECONOMY,
    conquest_tiles,
    find_optimum,
    max_troops,
    optimal_threshold_theory,
    regen,
    simulate,
    tile_budget_cost,
)


def test_engine_constants() -> None:
    assert FIRST_DECISION_TICK == 2
    # spawn state: 52 tiles -> ~121k max troops
    assert max_troops(52) == 2 * (52**0.6 * 1000 + 50000)
    assert abs(max_troops(52) - 121_000) < 5_000


def test_regen_argmax_near_theory() -> None:
    # static argmax ~0.418 at early-game caps; dynamic optimum sits below it
    assert abs(optimal_threshold_theory(1e5) - 0.418) < 0.005
    # spot-check the formula: fresh spawn regenerates ~330 troops/tick
    assert abs(regen(25000.0, 52.0) - 330.27) < 0.1


def test_tile_budget_cost_clamp() -> None:
    assert tile_budget_cost(100_000.0) == 5.0
    assert tile_budget_cost(6600.0) == 5.0
    assert tile_budget_cost(330.0) == 100.0
    assert tile_budget_cost(100.0) == 100.0


def test_conquest_exact_cost() -> None:
    # troop conservation at 16/tile when budget is ample
    assert conquest_tiles(16000.0, 1e9) == (1000, 0.0)
    # budget-limited path through all three cost regions (flat 5 while
    # w >= 6600, 33000/w down to 330, flat 100 below): 849 tiles
    assert conquest_tiles(16000.0, 5000.0) == (849, 2416.0)
    # no troops or no budget -> no conquest
    assert conquest_tiles(0.0, 5000.0) == (0, 0.0)
    assert conquest_tiles(100.0, 0.0) == (0, 100.0)


def test_simulate_deterministic() -> None:
    first = simulate(0.36, 0.005, interval=1)
    second = simulate(0.36, 0.005, interval=1)
    assert first == second


def test_simulate_pinned_crossings() -> None:
    cases = [
        ((0.36, 0.005, 1), 7802),
        ((0.375, 0.05, 10), 7808),
        ((0.375, 0.065, 20), 7808),
        ((0.38, 0.095, 30), 7815),
        ((0.37, 0.115, 40), 7818),
        ((0.0, 0.12, 50), 7858),
        ((0.37, 0.15, 50), 7858),
        ((0.40, 0.10, 1), 7817),
        # nation-cadence optima (Hard attackRate = U{45..60})
        ((0.38, 0.15, 45), 7846),
        ((0.38, 0.15, 52), 7824),
        ((0.37, 0.18, 60), 7880),
    ]
    for (threshold, ratio, interval), expected in cases:
        got = simulate(threshold, ratio, interval=interval)["crossing_tick"]
        assert got == expected, (threshold, ratio, interval, got)


def test_nation_economy_matches_hard_and_decomposes() -> None:
    # hard == human economy: scaling params default to identity
    assert NATION_ECONOMY["hard"] == (25000.0, 1.0, 1.0)
    base = simulate(0.36, 0.005, interval=1)["crossing_tick"]
    hard = simulate(0.36, 0.005, interval=1, max_mult=1.0, start_troops=25000.0)
    assert hard["crossing_tick"] == base
    # optimal-play crossings per economy, pinned at the full-precision
    # 8-start optima logged in verify_results.json (milliseconds each).
    # The residual vs the observed nation declared ticks
    # (easy 15551, medium 11461, hard 9151, impossible 7691) is the behavior gap.
    optima = {
        "easy": (0.3923187255859375, 0.009194641113281235, 13214),
        "medium": (0.38263789415359495, 0.049872417449951176, 9729),
        "hard": (0.36435546875, 0.013359374999999991, 7802),
        "impossible": (0.34831542968749996, 0.005058593749999984, 6556),
    }
    for name, (start, mm, rm) in NATION_ECONOMY.items():
        th, ra, expected = optima[name]
        got = simulate(
            th, ra, interval=1, max_mult=mm, regen_mult=rm, start_troops=start
        )["crossing_tick"]
        assert got == expected, (name, got)
    # optimizer plumbing under a non-human economy: 2 starts land within
    # the same +-6 tick band the game verification tolerates.
    opt = find_optimum(
        1,
        starts=((0.4, 0.10), (0.42, 0.05)),
        max_mult=1.25,
        regen_mult=1.05,
        start_troops=31250.0,
    )
    assert opt["crossing_tick"] <= 6556 + 6


def test_simulate_far_field_and_death_spiral() -> None:
    assert simulate(0.2, 0.01, interval=1)["crossing_tick"] == 8908
    assert simulate(0.5, 0.1, interval=1)["crossing_tick"] == 8188
    assert simulate(0.36, 0.5, interval=1)["crossing_tick"] == 8386
    assert simulate(0.0, 0.1, interval=1)["crossing_tick"] == float("inf")


def test_optimizer_improves_and_is_deterministic() -> None:
    # two starts keep the unit suite fast; the full 8-start global run is
    # exercised by verify_optimum.py and pinned in verify_results.json
    first = find_optimum(1, starts=((0.4, 0.10), (0.42, 0.05)))
    second = find_optimum(1, starts=((0.4, 0.10), (0.42, 0.05)))
    assert first == second
    assert first["crossing_tick"] <= 7810  # beats the old grid best (7817)
    assert 0.0 < first["threshold"] < 0.95
    assert 0.001 <= first["ratio"] <= 1.0
