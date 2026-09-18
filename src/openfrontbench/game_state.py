from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GameState:
    scenario_name: str
    seed: int
    tick: int = 0
