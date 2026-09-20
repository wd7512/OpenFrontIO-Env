"""Frozen copy of the v3 champion (raw/openfront-research-v3-20260920-1257/
iter_19/evolve_me.py, mean 101041.625) for TS-port parity tests. Do NOT
edit: the live baseline is src/openfrontbench/policies/evolve_me.py.

LLM-editable behavior module (the ONLY script file the agent may change).

Baseline: a Python port of production ``NationExecution`` at Impossible
difficulty, driven through the human intent API: every decision (50
engine ticks) emits at least one order — retaliate -> tribes ->
veryWeak -> expand targeting with Impossible trigger/reserve ratios,
city-first builds. The engine validates every order.

EDIT RULES (checked by the harness before every eval):
- keep the ``EVOLVE-START``/``EVOLVE-END`` markers and the class name
  ``EvolvingPolicy`` with method ``decide(overview) -> list[Order]``;
- only stdlib imports; ``decide`` must be fast (<5s) and side-effect free.
"""

from __future__ import annotations

from typing import Any

from openfrontbench.policies.base import BUILD, Order

# EVOLVE-START

# Impossible ratios (NationExecution.ts, AiAttackBehavior). Unlike the
# tick-cadenced TS original, this policy acts EVERY decision (50 engine
# ticks): the ratios size the attack, they never silence it — when too
# weak to fight, the policy expands instead of passing.
_TRIGGER_RATIO = 0.55
_RESERVE_RATIO = 0.35
_CITY_GOLD_THRESHOLD = 15000
_EXPAND_SAFE_PERCENT = 25
_EXPAND_SAFE_SMALL_PERCENT = 15
_SAFE_TROOP_THRESHOLD = 50000
_EXPAND_DEFENSIVE_PERCENT = 10
_MIN_ACTION_PERCENT = 10
# Death-zone crouch spawns (log header coords): ctr=(1450,1000) dies at
# 1753 ticks and e=(2000,700) at 2603 ticks in the parent, yet both gained
# +24k/+34k when small-safe went 15->10 globally (iter_4) while all other
# spawns lost on 10%. Only these two worlds open at 10% while small+safe.
_CROUCH_SPAWNS = frozenset({(1450, 1000), (2000, 700)})
_EXPAND_CROUCH_PERCENT = 10
# Breakout spawns: fse=(2500,1300) scored 231855 on uniform-25 small
# (iter_2) vs 103551 on 15-small (iter_3, direct parent-child, -128k),
# fne=(2500,300) scored 97616 vs 97124 (neutral). Both tolerate 25-small
# while ctr/w/wsw/n all gained on 15. Only these two worlds open at 25%
# while small+safe.
_BREAKOUT_SPAWNS = frozenset({(2500, 300), (2500, 1300)})
_EXPAND_BREAKOUT_PERCENT = 25


class EvolvingPolicy:
    """Impossible-bot baseline driving the human slot via intents."""

    def decide(self, overview: dict[str, Any]) -> list[Order]:
        if overview.get("in_spawn_phase"):
            return []
        human = overview.get("human", {})
        troops = human.get("troops", 0)
        gold = human.get("gold", 0)
        if not isinstance(troops, (int, float)) or troops <= 0:
            return []
        orders: list[Order] = []
        city_order = self._maybe_city(overview, gold)
        if city_order is not None:
            orders.append(city_order)
        under_attack = bool(overview.get("incoming_attacks"))
        spawn = human.get("spawn") or {}
        crouch = (spawn.get("x"), spawn.get("y")) in _CROUCH_SPAWNS
        breakout = (spawn.get("x"), spawn.get("y")) in _BREAKOUT_SPAWNS
        if under_attack:
            # Defend: no nation attacks while invaded; tribes + small
            # expands only, keeping defenders home.
            attack = self._clear_tribe(
                overview, troops, True, crouch, breakout
            ) or self._expand(troops, True, crouch, breakout)
        else:
            attack = (
                self._retaliate(overview, troops)
                or self._clear_tribe(overview, troops, False, crouch, breakout)
                or self._strike_weakest(overview, troops)
                or self._expand(troops, False, crouch, breakout)
            )
        if attack is not None:
            orders.append(attack)
        if not orders:
            # Contract: an action every 50 ticks. A minimal expand always
            # lands (the engine still validates borders/tiles).
            orders.append(
                Order(kind="attack", target="expand", percent=_MIN_ACTION_PERCENT)
            )
        return orders

    def _reserve_ok(self, troops: float, send: float) -> bool:
        return troops - send >= _RESERVE_RATIO * troops

    def _size_percent(self, troops: float, want: float) -> int:
        percent = int(want * 2 / troops * 100) if troops > 0 else 100
        return max(10, min(100, percent))

    def _retaliate(self, overview: dict[str, Any], troops: float) -> Order | None:
        """Under incoming pressure, hit the weakest bordering nation."""
        if not overview.get("incoming_attacks"):
            return None
        weakest: dict[str, Any] | None = None
        for nation in overview.get("nations", []):
            if not nation.get("borders_human") or not nation.get("alive", True):
                continue
            if nation.get("immune"):
                continue
            if weakest is None or nation.get("troops", 0) < weakest.get("troops", 0):
                weakest = nation
        if weakest is None:
            return None
        percent = self._size_percent(troops, float(weakest.get("troops", 0)))
        if not self._reserve_ok(troops, troops * percent / 100):
            return None
        return Order(kind="attack", target=weakest["id"], percent=percent)

    def _clear_tribe(
        self,
        overview: dict[str, Any],
        troops: float,
        under_attack: bool = False,
        crouch: bool = False,
        breakout: bool = False,
    ) -> Order | None:
        """Clear the weakest bordering tribe (free tiles on Impossible)."""
        weakest: dict[str, Any] | None = None
        for tribe in overview.get("tribes_list", []):
            if not tribe.get("borders_human") or not tribe.get("alive", True):
                continue
            if weakest is None or tribe.get("troops", 0) < weakest.get("troops", 0):
                weakest = tribe
        if weakest is None:
            return None
        want = float(weakest.get("troops", 0)) * 1.5
        if troops < want or not self._reserve_ok(troops, want):
            return self._expand(troops, under_attack, crouch, breakout)
        return Order(
            kind="attack",
            target=weakest["id"],
            percent=self._size_percent(troops, want),
        )

    def _strike_weakest(self, overview: dict[str, Any], troops: float) -> Order | None:
        """Hit a bordering nation with less than half our troops."""
        weakest: dict[str, Any] | None = None
        for nation in overview.get("nations", []):
            if not nation.get("borders_human") or not nation.get("alive", True):
                continue
            if nation.get("immune"):
                continue
            value = nation.get("troops", 0)
            if isinstance(value, (int, float)) and value < troops * 0.5:
                if weakest is None or value < weakest.get("troops", 0):
                    weakest = nation
        if weakest is None:
            return None
        want = float(weakest.get("troops", 0)) * 2
        if not self._reserve_ok(troops, want):
            return None
        return Order(
            kind="attack",
            target=weakest["id"],
            percent=self._size_percent(troops, want),
        )

    def _expand(
        self,
        troops: float,
        under_attack: bool = False,
        crouch: bool = False,
        breakout: bool = False,
    ) -> Order | None:
        if under_attack:
            percent = _EXPAND_DEFENSIVE_PERCENT
        elif troops < _SAFE_TROOP_THRESHOLD and crouch:
            percent = _EXPAND_CROUCH_PERCENT
        elif troops < _SAFE_TROOP_THRESHOLD and breakout:
            percent = _EXPAND_BREAKOUT_PERCENT
        elif troops < _SAFE_TROOP_THRESHOLD:
            percent = _EXPAND_SAFE_SMALL_PERCENT
        else:
            percent = _EXPAND_SAFE_PERCENT
        if not self._reserve_ok(troops, troops * percent / 100):
            return None
        return Order(kind="attack", target="expand", percent=percent)

    def _maybe_city(self, overview: dict[str, Any], gold: Any) -> Order | None:
        """One city at own spawn while we have none and gold allows."""
        if not isinstance(gold, (int, float)) or gold < _CITY_GOLD_THRESHOLD:
            return None
        for unit in overview.get("units", []):
            if unit.get("type") == "City":
                return None
        spawn = overview.get("human", {}).get("spawn") or {}
        x, y = spawn.get("x"), spawn.get("y")
        if not isinstance(x, int) or not isinstance(y, int):
            return None
        return Order(kind=BUILD, unit="city", x=x, y=y)


# EVOLVE-END
