"""Fixed benchmark scenarios. Small maps first; seeds fixed per scenario."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Scenario:
    name: str
    map: str
    nations: int
    difficulties: str
    seeds: tuple[int, ...]
    max_ticks: int


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        name="box-small-2nations",
        map="thebox",
        nations=2,
        difficulties="easy,easy",
        seeds=(42, 7, 99),
        max_ticks=20000,
    ),
    Scenario(
        name="box-small-4nations-mixed",
        map="thebox",
        nations=4,
        difficulties="easy,easy,impossible,impossible",
        seeds=(42, 7, 99),
        max_ticks=20000,
    ),
)
