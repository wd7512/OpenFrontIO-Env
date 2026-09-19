"""Narration — human-readable text formatting for LLM consumption.

Mirrors civ6-mcp narrate.py: pure functions, data in / string out, no I/O.
Full readers over the vendored core land in step 2; this stub formats the
minimal observation (tick + scenario) so the pipeline is exercisable now.
"""

from __future__ import annotations

from typing import Mapping


def narrate_overview(state: Mapping[str, object]) -> str:
    tick = state.get("tick", "?")
    scenario = state.get("scenario", "?")
    return f"tick={tick} scenario={scenario}"
