"""Explicit spawn override on GameSession (code-evo fixed spawns)."""

from __future__ import annotations

from typing import Any

import pytest

from openfrontbench.session import GameSession, SessionError


def test_explicit_spawn_matching_boot_works() -> None:
    session = GameSession()
    started = session.start(spawn=(50, 50))
    assert started["status"] == "started"
    assert started["human"]["tiles"] > 0
    session.close()


def test_spawn_rejects_bad_shapes() -> None:
    bad_values: list[Any] = [(50,), (50, 50, 50), "50,50", (True, 50), (50.5, 50)]
    for bad in bad_values:
        session = GameSession()
        with pytest.raises(SessionError):
            session.start(spawn=bad)
