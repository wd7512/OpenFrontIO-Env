"""Diplomacy parity at engine level: alliances, embargo, donate.

Humans request/extend/break alliances, reject incoming requests, embargo
players, and donate gold/troops. All ride the production intent paths via
Executor.createExec. The engine (including nation AI) decides outcomes;
the adapter exposes the orders and projects the relations.
"""

from __future__ import annotations

import pytest

from openfront_mcp.engine import EngineWorker, EngineError


def _diplo() -> EngineWorker:
    from openfront_mcp.engine import PLAINS_MAP_DIR

    return EngineWorker(map_dir=PLAINS_MAP_DIR)


def _start(engine: EngineWorker) -> dict:
    return engine.start(nations=1, spawn=(50, 50), tribes=2)


def test_alliance_request_recorded() -> None:
    with _diplo() as engine:
        started = _start(engine)
        assert started["alliances"] == []
        assert started["alliance_requests"] == {"incoming": [], "outgoing": []}

        engine.alliance_request("nation-1")
        after = engine.advance(5)
        # The nation AI answers on its own schedule: either allied already
        # or the request is still pending — but it must be one of the two.
        allied = [a["id"] for a in after["alliances"]]
        outgoing = after["alliance_requests"]["outgoing"]
        assert allied == ["nation-1"] or outgoing == ["nation-1"]


def test_alliance_request_bad_target_rejected() -> None:
    with _diplo() as engine:
        _start(engine)
        with pytest.raises(EngineError):
            engine.alliance_request("nation-9")
        with pytest.raises(EngineError):
            engine.alliance_request("everyone")


def test_embargo_start_and_stop() -> None:
    with _diplo() as engine:
        _start(engine)
        engine.embargo("nation-1", "start")
        flagged = engine.advance(5)
        assert [e["id"] for e in flagged["embargoes"]] == ["nation-1"]

        engine.embargo("nation-1", "stop")
        cleared = engine.advance(5)
        assert cleared["embargoes"] == []


def test_embargo_bad_action_rejected() -> None:
    with _diplo() as engine:
        _start(engine)
        with pytest.raises(EngineError):
            engine.embargo("nation-1", "forever")


def test_donate_troops_refused_without_alliance() -> None:
    # Production rule: donations need friendly (allied) recipients, and the
    # nation AI never answers our request — so the order is accepted but
    # lands nothing, exactly like a human donating to a stranger. 20000 is
    # chosen to dwarf 50 ticks of troop income (~18k): a real deduction
    # would read negative, refusal reads positive.
    with _diplo() as engine:
        before = _start(engine)
        human_before = before["human"]["troops"]

        engine.donate_troops("nation-1", 20000)
        after = engine.advance(50)
        assert after["human"]["troops"] - human_before > 0


def test_donate_gold_refused_without_alliance() -> None:
    # Same friendly-only rule as troops. 20000 dwarfs 50 ticks of gold
    # income: a real deduction would read deeply negative, refusal positive.
    with _diplo() as engine:
        _start(engine)
        for _ in range(10):
            engine.attack("expand", 20000)
            engine.advance(50)
        funded = engine.advance(1)
        assert int(funded["human"]["gold"]) >= 40000
        human_before = int(funded["human"]["gold"])

        engine.donate_gold("nation-1", 20000)
        after = engine.advance(50)
        assert int(after["human"]["gold"]) - human_before > 0


def test_donate_bad_amount_rejected() -> None:
    with _diplo() as engine:
        _start(engine)
        with pytest.raises(EngineError):
            engine.donate_gold("nation-1", 0)
        with pytest.raises(EngineError):
            engine.donate_troops("nation-1", -5)


def test_reject_unknown_requestor_rejected() -> None:
    with _diplo() as engine:
        _start(engine)
        with pytest.raises(EngineError):
            engine.alliance_reject("nation-1")


def test_break_alliance_accepted_without_alliance() -> None:
    # Humans can press break any time; with no alliance it lands nothing.
    # Acceptance (no error) is the parity bit.
    with _diplo() as engine:
        _start(engine)
        cleared = engine.break_alliance("nation-1")
        assert cleared["alliances"] == []


def test_extend_alliance_accepted_without_alliance() -> None:
    # Same contract as break: accepted, lands nothing without an alliance.
    with _diplo() as engine:
        _start(engine)
        after = engine.alliance_extend("nation-1")
        assert after["alliances"] == []


def test_diplo_bad_targets_rejected() -> None:
    with _diplo() as engine:
        _start(engine)
        with pytest.raises(EngineError):
            engine.alliance_extend("nation-9")
        with pytest.raises(EngineError):
            engine.break_alliance("tribe-99")
        with pytest.raises(EngineError):
            engine.embargo("everyone", "start")
