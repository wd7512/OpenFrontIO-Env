"""Baseline policy behavior on synthetic overviews."""

from __future__ import annotations

from typing import Any

from openfrontbench.policies.base import Order, apply_orders
from openfrontbench.policies.evolve_me import EvolvingPolicy


def _overview(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "in_spawn_phase": False,
        "winner": None,
        "human": {
            "troops": 100000,
            "gold": 0,
            "tiles": 100,
            "spawn": {"x": 50, "y": 50},
        },
        "nations": [],
        "tribes_list": [],
        "units": [],
        "incoming_attacks": [],
    }
    base.update(overrides)
    return base


def _attacking(policy: EvolvingPolicy, overview: dict[str, Any]) -> Order | None:
    attacks = [o for o in policy.decide(overview) if o.kind == "attack"]
    return attacks[0] if attacks else None


def test_spawn_phase_yields_no_orders() -> None:
    policy = EvolvingPolicy()
    assert policy.decide(_overview(in_spawn_phase=True)) == []


def test_acts_every_decision_outside_spawn_phase() -> None:
    policy = EvolvingPolicy()
    scenarios = [
        _overview(),
        _overview(
            human={"troops": 50, "gold": 0, "tiles": 5, "spawn": {"x": 1, "y": 2}}
        ),
        _overview(
            nations=[
                {
                    "id": "nation-1",
                    "troops": 9999999,
                    "alive": True,
                    "immune": False,
                    "borders_human": True,
                }
            ]
        ),
        _overview(
            tribes_list=[
                {
                    "id": "tribe-1",
                    "troops": 9999999,
                    "alive": True,
                    "borders_human": True,
                }
            ]
        ),
    ]
    for overview in scenarios:
        assert policy.decide(overview), "policy passed a decision with no action"


def test_expand_when_nothing_to_hit() -> None:
    policy = EvolvingPolicy()
    attack = _attacking(policy, _overview())
    assert attack is not None
    assert attack.target == "expand"


def test_clears_weakest_bordering_tribe() -> None:
    policy = EvolvingPolicy()
    overview = _overview(
        tribes_list=[
            {"id": "tribe-1", "troops": 5000, "alive": True, "borders_human": True},
            {"id": "tribe-2", "troops": 500, "alive": True, "borders_human": True},
            {"id": "tribe-9", "troops": 100, "alive": True, "borders_human": False},
        ]
    )
    attack = _attacking(policy, overview)
    assert attack is not None
    assert attack.target == "tribe-2"


def test_strikes_weak_bordering_nation() -> None:
    policy = EvolvingPolicy()
    overview = _overview(
        nations=[
            {
                "id": "nation-1",
                "troops": 900000,
                "alive": True,
                "immune": False,
                "borders_human": False,
            },
            {
                "id": "nation-2",
                "troops": 10000,
                "alive": True,
                "immune": False,
                "borders_human": True,
            },
        ]
    )
    attack = _attacking(policy, overview)
    assert attack is not None
    assert attack.target == "nation-2"


def test_city_order_at_spawn_when_rich_and_cityless() -> None:
    policy = EvolvingPolicy()
    overview = _overview(
        human={
            "troops": 100000,
            "gold": 20000,
            "tiles": 100,
            "spawn": {"x": 50, "y": 50},
        }
    )
    orders = policy.decide(overview)
    cities = [o for o in orders if o.kind == "build"]
    assert cities and cities[0].unit == "city"
    assert (cities[0].x, cities[0].y) == (50, 50)


def test_apply_orders_skips_rejections() -> None:
    class FakeSession:
        def order_attack(self, target: object, percent: object = 20) -> dict[str, Any]:
            if target == "nation-9":
                raise RuntimeError("rejected")
            return {"status": "attack-ordered"}

        def order_build(self, unit: object, x: object, y: object) -> dict[str, Any]:
            return {"status": "build-ordered"}

    outcomes = apply_orders(
        FakeSession(),
        [
            Order(kind="attack", target="expand", percent=20),
            Order(kind="attack", target="nation-9", percent=20),
            Order(kind="mystery"),
        ],
    )
    assert outcomes[0]["ok"] is True
    assert outcomes[1]["ok"] is False
    assert outcomes[2]["ok"] is False
