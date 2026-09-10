"""Smoke tools. Plain functions for now; FastMCP decorators arrive in step 2."""

from __future__ import annotations

import logging

from openfront_mcp import scenarios as _scenarios

log = logging.getLogger(__name__)

PIN = "v0.33.14 (577819ba0e1e13ecdbc8dede2ba33de542c88a67)"
CORE_SCOPE = "src/core only; client/server untouched"


def get_pin() -> str:
    return f"upstream-openfrontio {PIN}; scope: {CORE_SCOPE}"


def list_scenarios() -> str:
    names = [s.name for s in _scenarios.SCENARIOS]
    return "scenarios: " + ", ".join(names)


TOOLS = {
    "get_pin": get_pin,
    "list_scenarios": list_scenarios,
}
