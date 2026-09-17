"""Converter tests: replay tape -> schema-valid archived GameRecord.

Builds a real tape with the pinned engine, converts it with the node
script (which validates against the production GameRecordSchema), and
pins the production archive shape (empty turns dropped, humans only).
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from openfront_mcp.engine import EngineWorker, PLAINS_MAP_DIR

REPO_ROOT = Path(__file__).resolve().parent.parent
CONVERTER = REPO_ROOT / "scripts" / "build_game_record.ts"
ESBUILD = REPO_ROOT / "engine" / "node_modules" / ".bin" / "esbuild"
VENDOR_ROOT = REPO_ROOT / "vendor" / "OpenFrontIO"


def _convert(run_dir: Path) -> dict:
    bundle = run_dir / "converter.mjs"
    env = {
        "NODE_PATH": str(REPO_ROOT / "engine" / "node_modules"),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
    }
    # Vendor sources use tsconfig path aliases (resources/*); bundle with
    # esbuild exactly like the engine worker so they resolve.
    bundle_proc = subprocess.run(
        [
            str(ESBUILD),
            str(CONVERTER),
            "--bundle",
            "--platform=node",
            "--format=esm",
            f"--alias:resources={VENDOR_ROOT / 'resources'}",
            f"--outfile={bundle}",
        ],
        capture_output=True,
        text=True,
        timeout=180,
        cwd=str(REPO_ROOT),
        env=env,
    )
    assert bundle_proc.returncode == 0, bundle_proc.stderr[-2000:]
    proc = subprocess.run(
        ["node", str(bundle), str(run_dir)],
        capture_output=True,
        text=True,
        timeout=180,
        cwd=str(REPO_ROOT),
        env=env,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    return json.loads((run_dir / "game_record.json").read_text())


def test_converter_builds_valid_record(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OPENFRONT_RECORD_DIR", str(tmp_path))
    with EngineWorker(map_dir=PLAINS_MAP_DIR) as engine:
        engine.start(
            nations=1, difficulty="easy", map_size="full", spawn=None, tribes=0
        )
        engine.advance(60)
        engine.attack("expand", 20000)
        engine.advance(50)
        engine.save_record()
    record = _convert(tmp_path)
    assert record["version"] == "v0.0.2"
    assert record["info"]["gameID"] == "ENGINE01"
    assert len(record["info"]["players"]) == 1
    assert record["info"]["players"][0]["username"] == "Smoke"
    # Production archive shape: empty turns dropped, non-empty kept.
    tape = json.loads((tmp_path / "record.json").read_text())
    non_empty = sum(1 for t in tape["turns"] if t["intents"])
    assert len(record["turns"]) == non_empty > 0
    assert any(i.get("type") == "attack" for t in record["turns"] for i in t["intents"])
