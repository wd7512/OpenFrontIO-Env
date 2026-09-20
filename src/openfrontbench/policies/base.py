"""Policy interface between behavior code and the game session.

A policy reads the ``get_overview`` projection (see
``GameSession._project``) and returns a list of :class:`Order` values.
:func:`apply_orders` executes them against a live :class:`GameSession`,
skipping rejected orders (acceptance, not landing, is the contract —
the engine validates gold, costs, tiles and borders).

Only ``evolve_me.py`` in this package is LLM-editable; this file is the
stable harness side and must not be edited by the coding agent.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

log = logging.getLogger(__name__)

ATTACK = "attack"
BUILD = "build"


@dataclass(frozen=True)
class Order:
    """One intended action. ``kind`` is ``"attack"`` or ``"build"``."""

    kind: str
    target: str = "expand"
    percent: int = 20
    unit: str = "city"
    x: int = 0
    y: int = 0
    params: dict[str, Any] = field(default_factory=dict)


class Policy(Protocol):
    """Behavior module contract: pure decide, no engine access."""

    def decide(self, overview: dict[str, Any]) -> list[Order]:
        """Return orders for one decision from an overview projection."""
        ...


def apply_orders(session: Any, orders: list[Order]) -> list[dict[str, Any]]:
    """Execute *orders* against *session*; one outcome dict per order.

    Rejected orders are recorded (``ok: False``) and skipped — a policy
    is never killed by a single illegal order.
    """
    outcomes: list[dict[str, Any]] = []
    for order in orders:
        try:
            if order.kind == ATTACK:
                result = session.order_attack(order.target, order.percent)
            elif order.kind == BUILD:
                result = session.order_build(order.unit, order.x, order.y)
            else:
                outcomes.append({"ok": False, "error": f"unknown kind {order.kind!r}"})
                continue
            outcomes.append({"ok": True, "status": result.get("status")})
        except Exception as exc:
            log.debug("order skipped: %s", exc)
            outcomes.append({"ok": False, "error": str(exc)})
    return outcomes
