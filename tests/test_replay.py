"""Replay determinism gate: live game replays bit-for-bit on the client path.

Plays a short real game (Europe, nations + tribes so AI/RNG streams run),
converts the tape, replays it through createGameRunner (the exact function
the browser worker uses), and demands exact final tiles/troops. This is the
proof that game_record.json files reproduce our games in the real view.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from openfrontbench.engine import EUROPE_MAP_DIR, EngineWorker

REPO_ROOT = Path(__file__).resolve().parent.parent
ESBUILD = REPO_ROOT / "engine" / "node_modules" / ".bin" / "esbuild"
VENDOR_RES = REPO_ROOT / "vendor" / "OpenFrontIO" / "resources"


def _bundle(dst: Path, src: str) -> Path:
    out = dst / f"{src}.mjs"
    env = {
        "NODE_PATH": str(REPO_ROOT / "engine" / "node_modules"),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
    }
    proc = subprocess.run(
        [
            str(ESBUILD),
            str(REPO_ROOT / "scripts" / f"{src}.ts"),
            "--bundle",
            "--platform=node",
            "--format=esm",
            f"--alias:resources={VENDOR_RES}",
            f"--outfile={out}",
        ],
        capture_output=True,
        text=True,
        timeout=180,
        cwd=str(REPO_ROOT),
        env=env,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    return out


def _run(node: Path, *args: str) -> subprocess.CompletedProcess:
    env = {
        "NODE_PATH": str(REPO_ROOT / "engine" / "node_modules"),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
    }
    return subprocess.run(
        ["node", str(node), *[str(a) for a in args]],
        capture_output=True,
        text=True,
        timeout=600,
        cwd=str(REPO_ROOT),
        env=env,
    )


def test_tape_replays_bit_for_bit(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OPENFRONT_RECORD_DIR", str(tmp_path))
    live: dict = {}
    with EngineWorker(map_dir=EUROPE_MAP_DIR) as engine:
        engine.start(nations=2, difficulty="easy", spawn=None, tribes=10)
        engine.advance(60)
        engine.attack("expand", 20000)
        engine.advance(100)
        engine.save_record()
        live = engine._request({"cmd": "query"})
    want_tiles = live["human"]["tiles"]
    want_troops = live["human"]["troops"]

    converter = _bundle(tmp_path, "build_game_record")
    proc = _run(converter, tmp_path)
    assert proc.returncode == 0, proc.stderr[-2000:]

    verifier = _bundle(tmp_path, "replay_verify")
    proc = _run(verifier, tmp_path, want_tiles, want_troops)
    assert proc.returncode == 0, proc.stdout[-1000:] + proc.stderr[-2000:]
    assert json.loads((tmp_path / "game_record.json").read_text())["info"]["gameID"]
