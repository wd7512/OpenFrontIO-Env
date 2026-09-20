"""LLM-editable behavior module (the ONLY script file the agent may change).

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
_EXPAND_PERCENT = 20
_MIN_ACTION_PERCENT = 10


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
        attack = (
            self._retaliate(overview, troops)
            or self._clear_tribe(overview, troops)
            or self._strike_weakest(overview, troops)
            or self._expand(troops)
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

    def _clear_tribe(self, overview: dict[str, Any], troops: float) -> Order | None:
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
            return self._expand(troops)
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

    def _expand(self, troops: float) -> Order | None:
        percent = _EXPAND_PERCENT
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
