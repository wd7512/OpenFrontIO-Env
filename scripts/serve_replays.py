"""Two-level replay website: experiments, then games.

Usage: uv run python scripts/serve_replays.py [--raw RAW] [--port PORT]
    [--client-port CLIENT_PORT]

Scans <raw>/ for experiment dirs (each holding experiment.json) plus
legacy flat run dirs, converts every tape to a schema-valid
game_record.json with the repo's node converter, and serves:

  GET /            experiment list: one card per experiment with game
                   count, kind and best score
  GET /exp/<name>  suite page: one card per game with a direct replay link
  GET /game/<id>   archive endpoint the real client fetches (CORS open)

Direct links open the vendor client straight into the replay
(``http://localhost:<client-port>/w0/game/<id>?spectate``); with no live
lobby the client falls through to the archive record and replays the full
tape through the real engine renderer. Have the client running first
(``npm run start:client`` in vendor/OpenFrontIO).

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
import threading
from collections import Counter
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

from openfrontbench.experiment import read_experiment
from openfrontbench.paths import REPO_ROOT
from openfrontbench.run_summary import read_summary

log = logging.getLogger(__name__)

LEGACY_EXPERIMENT = "legacy-runs"

GAME_ID_RE = re.compile(r"^[A-Za-z0-9]{8}$")
ESBUILD = REPO_ROOT / "engine" / "node_modules" / ".bin" / "esbuild"
CONVERTER = REPO_ROOT / "scripts" / "build_game_record.ts"
VENDOR_RES = REPO_ROOT / "vendor" / "OpenFrontIO" / "resources"


def find_runs(raw_dir: Path) -> list[Path]:
    """Run dirs under raw_dir holding a record.json, oldest first.

    Legacy flat scan kept for back-compat; new code prefers
    :func:`find_experiments`.
    """
    if not raw_dir.is_dir():
        return []
    return sorted(
        (c for c in raw_dir.iterdir() if c.is_dir() and (c / "record.json").is_file()),
        key=lambda c: c.name,
    )


@dataclass
class Experiment:
    """One experiment: named dir, optional manifest, nested game dirs."""

    name: str
    meta: dict[str, Any]
    game_dirs: list[Path]


def _nearest_experiment(
    game_dir: Path, raw_dir: Path, cache: dict[Path, dict[str, Any] | None]
) -> tuple[str, dict[str, Any]] | None:
    """Nearest ancestor (up to raw root) holding ``experiment.json``."""
    parent = game_dir.parent
    while parent != raw_dir and raw_dir in parent.parents:
        if parent not in cache:
            cache[parent] = read_experiment(parent)
        meta = cache[parent]
        if meta is not None:
            return parent.relative_to(raw_dir).as_posix(), meta
        parent = parent.parent
    return None


def find_experiments(raw_dir: Path, max_depth: int = 4) -> list[Experiment]:
    """Group game dirs by nearest experiment manifest; leftovers go legacy.

    Any depth up to *max_depth* is scanned, so ``<exp>/attempt-N/`` and
    ``<exp>/iter-N-eval/games/<spawn>/`` layouts group correctly.
    """
    if not raw_dir.is_dir():
        return []
    groups: dict[str, Experiment] = {}
    order: list[str] = []
    cache: dict[Path, dict[str, Any] | None] = {}
    seen: set[Path] = set()
    for dirpath, dirnames, filenames in os.walk(raw_dir, followlinks=True):
        current = Path(dirpath)
        try:
            resolved = current.resolve()
        except OSError:
            continue
        if resolved in seen:
            dirnames[:] = []
            continue
        seen.add(resolved)
        current = Path(dirpath)
        try:
            depth = len(current.relative_to(raw_dir).parts)
        except ValueError:
            continue
        if current == raw_dir:
            depth = 0
        if depth > max_depth:
            dirnames[:] = []
            continue
        dirnames.sort()
        if "record.json" not in filenames and "summary.json" not in filenames:
            continue
        found = _nearest_experiment(current, raw_dir, cache)
        if found is None:
            name: str = LEGACY_EXPERIMENT
            meta: dict[str, Any] = {"name": LEGACY_EXPERIMENT, "kind": "legacy"}
        else:
            name, meta = found
        if name not in groups:
            groups[name] = Experiment(name=name, meta=meta, game_dirs=[])
            order.append(name)
        groups[name].game_dirs.append(current)
    named = sorted(
        (groups[n] for n in order if n != LEGACY_EXPERIMENT),
        key=lambda e: e.name,
    )
    for exp in named:
        exp.game_dirs.sort(key=lambda p: p.name)
    if LEGACY_EXPERIMENT in groups:
        legacy = groups[LEGACY_EXPERIMENT]
        legacy.game_dirs.sort(key=lambda p: p.name)
        named.append(legacy)
    return named


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


def _short_sha(value: Any) -> str | None:
    if isinstance(value, str) and len(value) >= 8:
        return value[:8]
    return None


def load_summary(run_dir: Path) -> dict[str, Any]:
    """Best-effort index card facts from summary.json, else live_result.json."""
    summary: dict[str, Any] = {"name": run_dir.name}
    unified = read_summary(run_dir)
    if unified:
        summary["experiment"] = unified.get("experiment")
        summary["pipeline"] = unified.get("pipeline")
        summary["model"] = unified.get("model")
        summary["policy"] = _short_sha(unified.get("policy_sha256"))
        config = unified.get("config")
        config = config if isinstance(config, dict) else {}
        scenario = unified.get("extra")
        scenario = scenario if isinstance(scenario, dict) else {}
        summary["scenario"] = (
            scenario.get("scenario") or unified.get("map") or config.get("scenario")
        )
        summary["spawn"] = unified.get("spawn_id")
        summary["difficulty"] = unified.get("difficulty")
        summary["max_decisions"] = config.get("max_decisions", config.get("max_ticks"))
        summary["decisions"] = unified.get("decisions")
        summary["tick_first"] = unified.get("tick_first")
        summary["tick_last"] = unified.get("tick_last")
        summary["winner"] = unified.get("winner")
        summary["tiles"] = unified.get("tiles_final")
        summary["troops"] = unified.get("troops_final")
        summary["tiles_peak"] = unified.get("tiles_peak")
        summary["score"] = unified.get("score")
        summary["wall"] = unified.get("wall_s")
        summary["tool_calls"] = unified.get("tool_calls")
        summary["cost"] = unified.get("cost")
        extra_metrics = scenario.get("metrics")
        summary["metrics"] = (
            extra_metrics if isinstance(extra_metrics, dict) else dict(config)
        )
        summary["tool_errors"] = unified.get("tool_errors")
    else:
        live: Any = {}
        if (run_dir / "live_result.json").is_file():
            try:
                live = json.loads(
                    (run_dir / "live_result.json").read_text(encoding="utf-8")
                )
            except (OSError, ValueError):
                live = {}
        if isinstance(live, dict) and live:
            summary["model"] = live.get("model")
            summary["scenario"] = live.get("scenario")
            summary["difficulty"] = live.get("difficulty")
            summary["max_decisions"] = live.get("max_decisions")
            summary["duration_s"] = live.get("duration_s")
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
                metrics = inner.get("metrics")
                if isinstance(metrics, dict):
                    summary["metrics"] = metrics
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


def _file_stamp(path: Path) -> tuple[int, int]:
    try:
        st = path.stat()
    except OSError:
        return (0, 0)
    return (st.st_mtime_ns, st.st_size)


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


class Registry:
    """Live view over ``raw/``: experiments, each a suite of games.

    New and still-growing runs join without restart: a game is
    re-converted whenever its tape or summary changes, and route IDs
    stay pinned per game once first staged, keeping shared watch links
    stable. A tape caught mid-write fails conversion and is retried on
    the next refresh.
    """

    def __init__(
        self,
        raw_dir: Path,
        bundle: Path,
        client_base: str,
        convert: Callable[[Path, Path], dict[str, Any]] = convert_run,
    ) -> None:
        self._raw = raw_dir
        self._bundle = bundle
        self._client_base = client_base
        self._convert = convert
        self._lock = threading.Lock()
        self._stamps: dict[str, tuple[int, int, int, int]] = {}
        self._route_ids: dict[str, str] = {}
        self._exp_of: dict[str, str] = {}
        self._records: dict[str, bytes] = {}
        self._summaries: dict[str, dict[str, Any]] = {}
        self._exp_index = render_experiments({})
        self._suites: dict[str, bytes] = {}

    def _next_route_id(self) -> str:
        used = set(self._route_ids.values())
        n = 1
        while f"OF{n:06d}" in used:
            n += 1
        return f"OF{n:06d}"

    def _game_key(self, exp_name: str, game_dir: Path) -> str:
        if exp_name == LEGACY_EXPERIMENT:
            return game_dir.name
        try:
            return game_dir.relative_to(self._raw).as_posix()
        except ValueError:
            return game_dir.name

    def refresh(self) -> bool:
        """Stage new or changed games; returns True when the view changed."""
        changed = False
        with self._lock:
            for exp in find_experiments(self._raw):
                for game_dir in exp.game_dirs:
                    key = self._game_key(exp.name, game_dir)
                    self._exp_of[key] = exp.name
                    record_stamp = _file_stamp(game_dir / "record.json")
                    summary_stamp = _file_stamp(game_dir / "summary.json")
                    live_stamp = _file_stamp(game_dir / "live_result.json")
                    stamp = (
                        record_stamp[0],
                        record_stamp[1],
                        summary_stamp[0] + live_stamp[0],
                        summary_stamp[1] + live_stamp[1],
                    )
                    if self._stamps.get(key) == stamp:
                        continue
                    if not (game_dir / "record.json").is_file():
                        summary = load_summary(game_dir)
                        summary["game_id"] = self._route_ids.get(key, "")
                        self._summaries[key] = summary
                        self._stamps[key] = stamp
                        changed = True
                        continue
                    try:
                        record = self._convert(game_dir, self._bundle)
                    except Exception as exc:
                        log.debug("run %s not stageable yet: %s", key, exc)
                        continue
                    route_id = self._route_ids.get(key)
                    if route_id is None:
                        route_id = self._next_route_id()
                        self._route_ids[key] = route_id
                    self._records[route_id] = json.dumps(record).encode("utf-8")
                    summary = load_summary(game_dir)
                    summary["game_id"] = route_id
                    self._summaries[key] = summary
                    self._stamps[key] = stamp
                    changed = True
            if changed:
                self._rebuild_indexes()
        return changed

    def _rebuild_indexes(self) -> None:
        by_exp: dict[str, dict[str, dict[str, Any]]] = {}
        for key, summary in self._summaries.items():
            exp_name = self._exp_of.get(key, LEGACY_EXPERIMENT)
            by_exp.setdefault(exp_name, {})[key] = summary
        suites: dict[str, bytes] = {}
        overview: dict[str, dict[str, Any]] = {}
        for exp in find_experiments(self._raw):
            games = by_exp.get(exp.name, {})
            suites[exp.name] = render_index(games, self._client_base)
            scores = [
                s.get("score")
                for s in games.values()
                if isinstance(s.get("score"), (int, float))
            ]
            overview[exp.name] = {
                "kind": exp.meta.get("kind"),
                "games": len(games),
                "best_score": max(scores) if scores else None,
                "created": exp.meta.get("created_at"),
            }
        self._suites = suites
        self._exp_index = render_experiments(overview)

    def snapshot(
        self,
    ) -> tuple[dict[str, bytes], bytes, dict[str, bytes]]:
        with self._lock:
            return dict(self._records), self._exp_index, dict(self._suites)

    def summaries(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return {name: dict(s) for name, s in self._summaries.items()}


def _cell(value: Any) -> str:
    if value is None:
        return "<td>&mdash;</td>"
    return f"<td>{html.escape(str(value))}</td>"


def _fmt_score(value: Any) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return f"{value:,.0f}"


def render_index(summaries: dict[str, dict[str, Any]], client_base: str) -> bytes:
    rows = []
    for name in sorted(summaries):
        s = summaries[name]
        game_id = s.get("game_id") or ""
        if game_id:
            link = f"{client_base}/w0/game/{game_id}?spectate"
            watch = (
                f'<td><a href="{html.escape(link)}">'
                f"{html.escape(str(game_id))} &#9654;</a></td>"
            )
        else:
            # No tape (ran before capture, or convert pending): no link at
            # all, so nothing looks watchable that is not.
            watch = "<td>&mdash;</td>"
        ticks = (
            f"{s['tick_first']}&ndash;{s['tick_last']}"
            if s.get("tick_first") is not None
            else None
        )
        duration = s.get("duration_s", s.get("wall"))
        wall = f"{duration:.0f}s" if isinstance(duration, (int, float)) else None
        metrics = s.get("metrics") or {}
        rows.append(
            "<tr>"
            f"<td>{html.escape(name)}</td>"
            f"{watch}"
            f"{_cell(s.get('model'))}"
            f"{_cell(s.get('policy'))}"
            f"{_cell(s.get('scenario'))}"
            f"{_cell(s.get('spawn'))}"
            f"{_cell(s.get('difficulty'))}"
            f"{_cell(s.get('max_decisions'))}"
            f"{_cell(s.get('decisions'))}"
            f"<td>{ticks or '&mdash;'}</td>"
            f"{_cell(s.get('winner'))}"
            f"{_cell(s.get('tiles'))}"
            f"{_cell(s.get('troops'))}"
            f"{_cell(_fmt_score(s.get('score')))}"
            f"{_cell(s.get('tool_calls'))}"
            f"{_cell(metrics.get('cities'))}"
            f"{_cell(metrics.get('attacks'))}"
            f"{_cell(metrics.get('attacks_engaged'))}"
            f"{_cell(metrics.get('attacks_after_50'))}"
            f"{_cell(metrics.get('tool_errors'))}"
            f"{_cell(s.get('tiles_peak', metrics.get('tiles_peak')))}"
            f"{_cell(wall)}"
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
        + "<table><tr><th>run</th><th>watch</th><th>model</th><th>policy</th>"
        "<th>scenario</th><th>spawn</th>"
        "<th>difficulty</th><th>max decisions</th><th>decisions</th><th>ticks</th>"
        "<th>winner</th><th>tiles</th><th>troops</th><th>score</th>"
        "<th>tool calls</th>"
        "<th>cities</th><th>atk</th><th>atk land</th><th>atk&gt;50</th>"
        "<th>tool errs</th><th>peak tiles</th>"
        "<th>wall</th><th>cost</th></tr>\n"
        + "".join(rows)
        + "\n</table></body></html>\n"
    )
    return page.encode("utf-8")


def render_experiments(
    overview: dict[str, dict[str, Any]], base_path: str = ""
) -> bytes:
    """Top-level page: one row per experiment linking to its suite."""
    rows = []
    for name in sorted(overview):
        info = overview[name]
        link = f"{base_path}/exp/{html.escape(name)}"
        rows.append(
            "<tr>"
            f'<td><a href="{link}">{html.escape(name)}</a></td>'
            f"{_cell(info.get('kind'))}"
            f"{_cell(info.get('games'))}"
            f"{_cell(_fmt_score(info.get('best_score')))}"
            f"{_cell(info.get('created'))}"
            "</tr>"
        )
    page = (
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">\n'
        "<title>OpenFrontBench experiments</title>\n"
        "<style>body{background:#111;color:#eee;font-family:sans-serif;margin:2em}\n"
        "table{border-collapse:collapse}td,th{border:1px solid #444;padding:.4em .7em}\n"
        "a{color:#7fd4ff}p.note{color:#aaa}</style>\n"
        "</head><body>\n"
        f"<h2>OpenFrontBench experiments ({len(rows)})</h2>\n"
        '<p class="note">Click an experiment to open its suite of runs. '
        "Watch links open the real client straight into the engine replay.</p>\n"
        + "<table><tr><th>experiment</th><th>kind</th><th>games</th>"
        "<th>best score</th><th>created</th></tr>\n"
        + "".join(rows)
        + "\n</table></body></html>\n"
    )
    return page.encode("utf-8")


def make_handler(view: Callable[[], tuple[dict[str, bytes], bytes, dict[str, bytes]]]):
    """Serve experiments, suites and the tape archive from a live view.

    The view is called per request, which is how the live ``Registry``
    lets new runs appear without a restart.
    """

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
            live_records, live_index, live_suites = view()
            if self.path == "/" or self.path == "/index.html":
                self._cors(200, len(live_index), "text/html; charset=utf-8")
                self.wfile.write(live_index)
                return
            parts = self.path.strip("/").split("/")
            data = None
            ctype = "application/json"
            if len(parts) == 2 and parts[0] == "exp":
                data = live_suites.get(parts[1])
                ctype = "text/html; charset=utf-8"
            elif len(parts) == 2 and parts[0] == "game":
                data = live_records.get(parts[1])
            if data is None:
                self._cors(404, 0, "text/plain")
                return
            self._cors(200, len(data), ctype)
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

    raw_dir = Path(args.raw)
    if not find_experiments(raw_dir):
        log.error("no experiments or runs under %s", args.raw)
        return 2
    client_base = f"http://localhost:{args.client_port}"
    with tempfile.TemporaryDirectory(prefix="openfront-replays-") as tmp:
        bundle = bundle_converter(Path(tmp))
        registry = Registry(raw_dir, bundle, client_base)
        registry.refresh()
        for name in sorted(registry.summaries()):
            s = registry.summaries()[name]
            log.info(
                "%s -> gameID %s tiles=%s troops=%s",
                name,
                s["game_id"],
                s.get("tiles"),
                s.get("troops"),
            )
        log.info("staged %d games", len(registry.summaries()))
        stop = threading.Event()

        def watch() -> None:
            # Fast enough that an attempt shows up while it is still being
            # played; the stamp check keeps unchanged tapes free.
            while not stop.wait(5.0):
                try:
                    if registry.refresh():
                        log.info(
                            "replay index refreshed: %d games",
                            len(registry.snapshot()[0]),
                        )
                except Exception:
                    log.exception("replay refresh failed")

        threading.Thread(target=watch, daemon=True).start()
        server = ThreadingHTTPServer(
            ("127.0.0.1", args.port), make_handler(registry.snapshot)
        )
        log.info(
            "replay index for %d games on http://127.0.0.1:%d (auto-refresh)",
            len(registry.snapshot()[0]),
            args.port,
        )
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            stop.set()
            server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
