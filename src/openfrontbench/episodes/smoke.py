"""Worked example episode driver: the plains-human-smoke scripted episode.

Every OpenFront-specific value lives here and only here: the scenario and
controller names, the MCP tool script, the engine bundle and map-asset
paths, the vendor-pin probe, and the result record's metric claims.
``benchmark.py`` takes this driver as an explicit input.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openfrontbench import pins as _pins
from openfrontbench.engine import DEFAULT_ENGINE_DIR, PLAINS_MAP_DIR
from openfrontbench.paths import REPO_ROOT
from openfrontbench.session import SMOKE_SCENARIO

ENGINE_BUNDLE_REL = "engine/dist/worker.mjs"
MAP_ASSET_DIR = "vendor/OpenFrontIO/tests/testdata/maps/plains"
MAP_ASSET_NAMES = ("manifest.json", "map.bin", "map4x.bin")


def _actual_vendor_pin() -> str | None:
    try:
        proc = subprocess.run(
            [
                "git",
                "-C",
                str(REPO_ROOT / "vendor" / "OpenFrontIO"),
                "rev-parse",
                "HEAD",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    value = proc.stdout.strip()
    return value if value else None


@dataclass(frozen=True)
class SmokeDriver:
    """The single-human, scripted-controller, no-opponent smoke episode."""

    scenario: str = SMOKE_SCENARIO
    controller: str = "scripted"
    allowed_scenarios: frozenset[str] = frozenset({SMOKE_SCENARIO})
    allowed_controllers: frozenset[str] = frozenset({"scripted"})
    server_module: str = "openfrontbench"
    decision_tool: str = "end_decision"
    source: str = "scripted_not_llm"
    completion_reason: str = "scripted maximum decisions reached"
    winner: Any = None
    metrics: dict[str, Any] = field(default_factory=dict)
    metrics_note: str = (
        "unavailable in smoke: the scripted controller records no "
        "strategic-query or commitment events, so PMR (proactive "
        "monitoring rate) and RAG@10 (reflection-action gap) cannot be "
        "scored from this trace"
    )
    engine_bundle_rel: str = ENGINE_BUNDLE_REL
    engine_bundle_path: Path = DEFAULT_ENGINE_DIR / "dist" / "worker.mjs"
    map_assets: tuple[tuple[str, Path], ...] = tuple(
        (f"{MAP_ASSET_DIR}/{name}", PLAINS_MAP_DIR / name) for name in MAP_ASSET_NAMES
    )
    vendor_tag: str = _pins.VENDOR_TAG
    vendor_pin: str = _pins.VENDOR_PIN

    def build_steps(self, max_decisions: int) -> list[tuple[str, dict[str, Any]]]:
        """Start, overview, one ``end_decision`` per decision, close."""
        steps: list[tuple[str, dict[str, Any]]] = [
            ("start_smoke_game", {}),
            ("get_overview", {}),
        ]
        steps.extend(
            ("end_decision", {"decision": n}) for n in range(1, max_decisions + 1)
        )
        steps.extend([("get_overview", {}), ("close_game", {})])
        return steps

    def probe_issues(self) -> tuple[str | None, list[str]]:
        """Check engine bundle, map assets, and vendored core pin."""
        issues: list[str] = []
        if not self.engine_bundle_path.is_file():
            issues.append(f"engine bundle missing: {self.engine_bundle_rel}")
        for label, path in self.map_assets:
            if not path.is_file():
                issues.append(f"map asset missing: {label}")
        actual = _actual_vendor_pin()
        if actual is None:
            issues.append("cannot verify vendor pin (git unavailable)")
        elif actual != self.vendor_pin:
            issues.append(
                f"vendor pin mismatch: expected {self.vendor_pin}, actual {actual}"
            )
        return actual, issues


SMOKE_DRIVER = SmokeDriver()
