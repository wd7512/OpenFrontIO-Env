"""Tiny replay website: direct links to view every raw/ game in the real client.

Usage: uv run python scripts/serve_replays.py [--raw RAW] [--port PORT]
    [--client-port CLIENT_PORT]

Scans <raw>/ for run dirs (each holding record.json), converts every tape to
a schema-valid game_record.json with the repo's node converter, and serves:

  GET /            index page: one card per game with a direct replay link
  GET /game/<id>   archive endpoint the real client fetches (CORS open)

Direct links open the vendor client straight into the replay
(``http://localhost:<client-port>/w0/game/<id>?spectate``); with no live
lobby the client falls through to the archive record and replays the full
tape through the real engine renderer. Have the client running first
(``npm run start:client`` in vendor/OpenFrontIO, serves :9000).

raw/ is never modified: conversion output is moved away and only record
bytes are served from memory. Every engine run tapes gameID ENGINE01, so
route IDs (OF000001, ...) only select which pristine record to serve: the
record bytes are NEVER rewritten, because the engine seeds its RNG from
``simpleHash(gameID)`` and any rewrite would reseed the replay into a
different world than the live game.
"""

from __future__ import annotations

import argparse
import html
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from openfront_mcp.paths import REPO_ROOT

log = logging.getLogger(__name__)

GAME_ID_RE = re.compile(r"^[A-Za-z0-9]{8}$")
ESBUILD = REPO_ROOT / "engine" / "node_modules" / ".bin" / "esbuild"
CONVERTER = REPO_ROOT / "scripts" / "build_game_record.ts"
VENDOR_RES = REPO_ROOT / "vendor" / "OpenFrontIO" / "resources"


def find_runs(raw_dir: Path) -> list[Path]:
    """Run dirs under raw_dir holding a record.json, oldest first."""
    if not raw_dir.is_dir():
        return []
    return sorted(
        (c for c in raw_dir.iterdir() if c.is_dir() and (c / "record.json").is_file()),
        key=lambda c: c.name,
    )


def assign_ids(names: list[str], original: dict[str, str]) -> dict[str, str]:
    """Unique route ID per run; originals are only used to detect collisions.

    Route IDs select which record to serve and never rewrite it: every run
    tapes ENGINE01, so colliding originals get OF00000N routes while the
    served bytes keep the live gameID (and its RNG seed) intact.
    """
    counts = Counter(original.values())
    out: dict[str, str] = {}
    n = 0
    for name in sorted(names):
        oid = original.get(name, "")
        if oid and GAME_ID_RE.fullmatch(oid) and counts[oid] == 1:
            out[name] = oid
        else:
            n += 1
            out[name] = f"OF{n:06d}"
    return out


def load_summary(run_dir: Path) -> dict[str, Any]:
    """Best-effort index card facts from live_result.json + record.json."""
    summary: dict[str, Any] = {"name": run_dir.name}
    try:
        live = json.loads((run_dir / "live_result.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        live = {}
    if isinstance(live, dict):
        summary["model"] = live.get("model")
        summary["scenario"] = live.get("scenario")
        summary["difficulty"] = live.get("difficulty")
        summary["max_decisions"] = live.get("max_decisions")
        inner = live.get("summary", {})
        if isinstance(inner, dict):
            summary["decisions"] = len(inner.get("decisions", []) or [])
            ticks = inner.get("ticks", []) or []
            if ticks:
                summary["tick_first"] = ticks[0]
                summary["tick_last"] = ticks[-1]
            summary["winner"] = inner.get("winner")
            summary["tool_calls"] = inner.get("tool_calls")
            summary["cost"] = inner.get("cost")
            human = inner.get("final_human", {})
            if isinstance(human, dict):
                summary["tiles"] = human.get("tiles")
                summary["troops"] = human.get("troops")
    try:
        tape = json.loads((run_dir / "record.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        tape = {}
    if isinstance(tape, dict):
        turns = tape.get("turns", []) or []
        summary["turns_total"] = len(turns)
        summary["turns_nonempty"] = sum(1 for t in turns if t.get("intents"))
        summary["tape_ticks"] = tape.get("ticks")
        summary["tape_game_id"] = tape.get("gameId")
    return summary


def bundle_converter(dst: Path) -> Path:
    """Bundle the TS converter exactly like the replay tests do."""
    if not ESBUILD.is_file():
        raise RuntimeError(f"esbuild not found: {ESBUILD}")
    out = dst / "build_game_record.mjs"
    env = {
        "NODE_PATH": str(REPO_ROOT / "engine" / "node_modules"),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
    }
    proc = subprocess.run(
        [
            str(ESBUILD),
            str(CONVERTER),
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
    if proc.returncode != 0:
        raise RuntimeError(f"esbuild failed: {proc.stderr[-2000:]}")
    return out


def convert_run(run_dir: Path, bundle: Path) -> dict[str, Any]:
    """Convert one tape; converter output is removed so raw/ is untouched."""
    env = {
        "NODE_PATH": str(REPO_ROOT / "engine" / "node_modules"),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
    }
    produced = run_dir / "game_record.json"
    try:
        proc = subprocess.run(
            ["node", str(bundle), str(run_dir)],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(REPO_ROOT),
            env=env,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"converter failed: {proc.stderr[-2000:]}")
        return json.loads(produced.read_text(encoding="utf-8"))
    finally:
        try:
            produced.unlink()
        except OSError:
            pass


def stage_records(
    runs: list[Path], bundle: Path
) -> tuple[dict[str, bytes], dict[str, dict[str, Any]]]:
    """Convert every run; return ({routeID: pristine record bytes}, summaries)."""
    converted: dict[str, dict[str, Any]] = {}
    originals: dict[str, str] = {}
    for run_dir in runs:
        record = convert_run(run_dir, bundle)
        converted[run_dir.name] = record
        info = record.get("info", {})
        originals[run_dir.name] = (
            info.get("gameID", "") if isinstance(info, dict) else ""
        )
    ids = assign_ids([r.name for r in runs], originals)
    records: dict[str, bytes] = {}
    summaries: dict[str, dict[str, Any]] = {}
    for run_dir in runs:
        route_id = ids[run_dir.name]
        records[route_id] = json.dumps(converted[run_dir.name]).encode("utf-8")
        summary = load_summary(run_dir)
        summary["game_id"] = route_id
        summaries[run_dir.name] = summary
    return records, summaries


def _cell(value: Any) -> str:
    if value is None:
        return "<td>&mdash;</td>"
    return f"<td>{html.escape(str(value))}</td>"


def render_index(summaries: dict[str, dict[str, Any]], client_base: str) -> bytes:
    rows = []
    for name in sorted(summaries):
        s = summaries[name]
        link = f"{client_base}/w0/game/{s['game_id']}?spectate"
        ticks = (
            f"{s['tick_first']}&ndash;{s['tick_last']}"
            if s.get("tick_first") is not None
            else None
        )
        rows.append(
            "<tr>"
            f"<td>{html.escape(name)}</td>"
            f'<td><a href="{html.escape(link)}">{html.escape(str(s["game_id"]))} &#9654;</a></td>'
            f"{_cell(s.get('scenario'))}"
            f"{_cell(s.get('difficulty'))}"
            f"{_cell(s.get('decisions'))}"
            f"<td>{ticks or '&mdash;'}</td>"
            f"{_cell(s.get('winner'))}"
            f"{_cell(s.get('tiles'))}"
            f"{_cell(s.get('troops'))}"
            f"{_cell(s.get('cost'))}"
            "</tr>"
        )
    page = (
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">\n'
        "<title>OpenFrontBench replays</title>\n"
        "<style>body{background:#111;color:#eee;font-family:sans-serif;margin:2em}\n"
        "table{border-collapse:collapse}td,th{border:1px solid #444;padding:.4em .7em}\n"
        "a{color:#7fd4ff}p.note{color:#aaa}</style>\n"
        "</head><body>\n"
        f"<h2>OpenFrontBench replays ({len(rows)} games)</h2>\n"
        '<p class="note">Links open the real client straight into the engine replay. '
        "Client must be running (<code>npm run start:client</code> in "
        "vendor/OpenFrontIO).</p>\n"
        + "<table><tr><th>run</th><th>watch</th><th>scenario</th><th>difficulty</th>\n"
        "<th>decisions</th>"
        "<th>ticks</th><th>winner</th><th>tiles</th><th>troops</th><th>cost</th></tr>\n"
        + "".join(rows)
        + "\n</table></body></html>\n"
    )
    return page.encode("utf-8")


def make_handler(records: dict[str, bytes], index: bytes):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):  # noqa: A002 - stdlib signature
            pass

        def _cors(self, status: int, length: int, ctype: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(length))
            self.end_headers()

        def do_GET(self):
            if self.path == "/" or self.path == "/index.html":
                self._cors(200, len(index), "text/html; charset=utf-8")
                self.wfile.write(index)
                return
            parts = self.path.strip("/").split("/")
            data = None
            if len(parts) == 2 and parts[0] == "game":
                data = records.get(parts[1])
            if data is None:
                self._cors(404, 0, "text/plain")
                return
            self._cors(200, len(data), "application/json")
            self.wfile.write(data)

        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

    return Handler


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="replay website for raw/ runs")
    parser.add_argument("--raw", default=str(REPO_ROOT / "raw"))
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--client-port", type=int, default=9000)
    args = parser.parse_args(argv)

    runs = find_runs(Path(args.raw))
    if not runs:
        log.error("no runs with record.json under %s", args.raw)
        return 2
    client_base = f"http://localhost:{args.client_port}"
    with tempfile.TemporaryDirectory(prefix="openfront-replays-") as tmp:
        bundle = bundle_converter(Path(tmp))
        records, summaries = stage_records(runs, bundle)
        index = render_index(summaries, client_base)
        for name in sorted(summaries):
            s = summaries[name]
            log.info(
                "%s -> gameID %s tiles=%s troops=%s",
                name,
                s["game_id"],
                s.get("tiles"),
                s.get("troops"),
            )
        server = ThreadingHTTPServer(
            ("127.0.0.1", args.port), make_handler(records, index)
        )
        log.info(
            "replay index for %d games on http://127.0.0.1:%d",
            len(records),
            args.port,
        )
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
