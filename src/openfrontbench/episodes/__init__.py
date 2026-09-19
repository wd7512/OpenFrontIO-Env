"""Episode driver protocol: the seam between benchmark core and example.

``benchmark.py`` owns the generic process (config-shape validation, atomic
writes, ordered tracing, manifest hashing, episode orchestration). An
``EpisodeDriver`` supplies everything domain-specific: which scenarios and
controllers exist, which MCP server module to spawn, which tool counts as
a decision, what the result record claims, and which pinned artifacts the
manifest must verify. See ``smoke.py`` for the single worked example.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class EpisodeDriver(Protocol):
    """Domain specifics for one benchmark episode kind."""

    scenario: str
    controller: str
    allowed_scenarios: frozenset[str]
    allowed_controllers: frozenset[str]
    server_module: str
    decision_tool: str
    source: str
    completion_reason: str
    winner: Any
    metrics: dict[str, Any]
    metrics_note: str
    engine_bundle_rel: str
    engine_bundle_path: Path
    map_assets: tuple[tuple[str, Path], ...]
    vendor_tag: str
    vendor_pin: str

    def build_steps(self, max_decisions: int) -> list[tuple[str, dict[str, Any]]]:
        """Return the ordered (tool, arguments) script for an episode."""
        ...

    def probe_issues(self) -> tuple[str | None, list[str]]:
        """Return ``(actual_pin, issues)`` for pinned-artifact integrity."""
        ...
