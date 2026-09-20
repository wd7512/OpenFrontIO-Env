"""Parity between the Python iter_19 champion and its TypeScript port.

P0 spike gate: the TS policy (``policies/evolve_me.ts``) must behave
bit-for-bit like ``tests/fixtures/iter19_evolve_me.py`` — same order
streams on recorded overviews, same episode outcomes on fixed worlds.
If these fail, the in-worker hook design is wrong and nothing else
gets built.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from openfrontbench.code_evo import evaluator as evo
from openfrontbench.code_evo.evaluator import EvalConfig, PolicyError
from openfrontbench.code_evo.spawns import Spawn
from openfrontbench.paths import REPO_ROOT

TS_POLICY = REPO_ROOT / "policies" / "evolve_me.ts"
TS_RUNNER = REPO_ROOT / "policies" / "decide_runner.ts"
CHAMPION = REPO_ROOT / "tests" / "fixtures" / "iter19_evolve_me.py"

CTR = Spawn(id="ctr", x=1450, y=1000)
S_SPAWN = Spawn(id="s", x=2000, y=1350)


def _node() -> str:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not on PATH")
    assert node is not None
    return node


def test_load_ts_policy_missing_file() -> None:
    with pytest.raises(PolicyError):
        evo.load_ts_policy(REPO_ROOT / "policies" / "does-not-exist.ts")


def test_load_ts_policy_missing_markers(tmp_path: Path) -> None:
    candidate = tmp_path / "policy.ts"
    candidate.write_text(
        "export class EvolvingPolicy { decide(o: any) { return []; } }\n",
        encoding="utf-8",
    )
    with pytest.raises(PolicyError):
        evo.load_ts_policy(candidate)


def test_load_ts_policy_missing_export(tmp_path: Path) -> None:
    candidate = tmp_path / "policy.ts"
    candidate.write_text(
        "// EVOLVE-START\nexport const x = 1;\n// EVOLVE-END\n",
        encoding="utf-8",
    )
    with pytest.raises(PolicyError):
        evo.load_ts_policy(candidate)


def test_load_ts_policy_banned_global(tmp_path: Path) -> None:
    candidate = tmp_path / "policy.ts"
    candidate.write_text(
        "// EVOLVE-START\nexport class EvolvingPolicy {\n"
        "  decide(o: any) { return Math.random() > 0.5 ? [] : []; }\n"
        "}\n// EVOLVE-END\n",
        encoding="utf-8",
    )
    with pytest.raises(PolicyError):
        evo.load_ts_policy(candidate)


def test_load_ts_policy_banned_import(tmp_path: Path) -> None:
    candidate = tmp_path / "policy.ts"
    candidate.write_text(
        "// EVOLVE-START\nimport { readFileSync } from 'node:fs';\n"
        "export class EvolvingPolicy { decide(o: any) { return []; } }\n"
        "// EVOLVE-END\n",
        encoding="utf-8",
    )
    with pytest.raises(PolicyError):
        evo.load_ts_policy(candidate)


def test_load_ts_policy_valid_bundles() -> None:
    """A valid TS policy bundles to ESM next to its source."""
    policy = evo.load_ts_policy(TS_POLICY)
    assert policy.bundle.is_file()
    assert policy.bundle.suffix == ".mjs"
    assert policy.bundle.parent == TS_POLICY.parent


def _record_overviews(
    decisions: int = 25,
) -> list[tuple[dict, list[tuple]]]:
    """Play CTR with the Python champion, capturing overview->orders pairs."""
    policy = evo.load_policy(CHAMPION)
    pairs: list[tuple[dict, list[tuple]]] = []

    class Recorder:
        def decide(self, overview: dict) -> list:
            orders = policy.decide(dict(overview))
            pairs.append((dict(overview), evo._serialize_orders(orders)))
            return orders

    config = EvalConfig(nations=52, tribes=400, max_ticks=decisions * 50)
    evo.run_episode(CTR, Recorder(), "europe", config, game_id="ts-parity-ctr")
    assert len(pairs) == decisions
    return pairs


def _ts_decide(pairs: list[tuple[dict, list]]) -> list[tuple]:
    """Replay recorded overviews through the TS policy; return order tuples."""
    payload = "\n".join(json.dumps(overview) for overview, _ in pairs) + "\n"
    completed = subprocess.run(
        [_node(), str(TS_RUNNER)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=120,
        cwd=REPO_ROOT,
    )
    assert completed.returncode == 0, completed.stderr[-2000:]
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    assert len(lines) == len(pairs)
    streams = []
    for line in lines:
        orders = json.loads(line)
        streams.append(
            tuple(
                (
                    order.get("kind"),
                    order.get("target"),
                    order.get("percent"),
                    order.get("unit"),
                    order.get("x"),
                    order.get("y"),
                )
                for order in orders
            )
        )
    return streams


def test_ts_order_stream_matches_python() -> None:
    """Same overviews in, same orders out — the port's core contract."""
    pairs = _record_overviews()
    ts_stream = _ts_decide(pairs)
    for index, ((_, expected), actual) in enumerate(zip(pairs, ts_stream)):
        assert actual == expected, f"decision {index} diverged"


def _episode_signature(episode: object) -> tuple:
    return (
        episode.ticks,  # type: ignore[attr-defined]
        episode.decisions,  # type: ignore[attr-defined]
        episode.tiles_peak,  # type: ignore[attr-defined]
        episode.final_tiles,  # type: ignore[attr-defined]
        episode.final_troops,  # type: ignore[attr-defined]
        episode.winner,  # type: ignore[attr-defined]
        episode.outcome,  # type: ignore[attr-defined]
        episode.score,  # type: ignore[attr-defined]
    )


@pytest.mark.parametrize("spawn", [CTR, S_SPAWN])
def test_ts_episode_matches_python(spawn: Spawn) -> None:
    """End-to-end parity on fixed legacy worlds: same game, same fate."""
    config = EvalConfig(nations=52, tribes=400, difficulty="medium")
    game_id = evo.game_id_for("ts-parity", spawn)
    expected = _episode_signature(
        evo.run_episode(
            spawn, evo.load_policy(CHAMPION), "europe", config, game_id=game_id
        )
    )
    actual = _episode_signature(
        evo.run_episode(
            spawn,
            evo.load_ts_policy(TS_POLICY),
            "europe",
            config,
            game_id=game_id,
        )
    )
    assert actual == expected
