---
name: serve-replay
description: Use when the user wants to watch a finished game replay, serve runs in the real game client, or view matches through the engine replay.
---

# Serve Replay

Serve finished runs through the replay index (`scripts/serve_replays.py`):
an experiment list; click an experiment for its suite of games, each with
a click-to-watch card opening the real client straight into the engine
replay. Nothing is written into the run dirs.

## Steps

1. Pick the source dir (default `raw/`, canonical home for experiment data).
   Done when: it holds at least one experiment dir (`experiment.json`)
   or legacy run dir containing `record.json` (`summary.json` alongside
   gives richer index cards; legacy `live_result.json` still works).
2. Start the vendor client (`vendor/OpenFrontIO`, `npm run start:client`,
   serves :9001 in this checkout — verify with the `Local:` log line) in
   the background. Done when: the client URL returns 200.
3. Start the replay index in the background. Done when: the log line
   `replay index for N games on http://127.0.0.1:8787` appears.
   ```bash
   nohup uv run python scripts/serve_replays.py [--raw raw/] [--port 8787] [--client-port 9001] > /tmp/replays/index.log 2>&1 &
   ```
   The script bundles the TS converter itself, converts every tape to a
   schema-valid `game_record.json` in temp space (run dirs untouched), and
   serves the experiment list plus per-experiment `/exp/<name>` suites and
   the `/game/<id>` archive endpoint (CORS open). Pass a subtree (or a dir
   of symlinks) as `--raw` to isolate one experiment set.
4. View: open `http://127.0.0.1:8787`, click an experiment, then a game's
   watch link (`http://localhost:9001/w0/game/<id>?spectate`). No live
   lobby exists, so the client falls through to the archive record and
   replays the full tape in the real renderer.

## Reference

- `gameID` must match `^[A-Za-z0-9]{8}$`; colliding engine IDs (every engine
  run tapes `ENGINE01`) are remapped to unique `OF00000N` form by the server.
- `ws proxy ECONNREFUSED` in the client log is harmless (no multiplayer
  server); the archive path runs.
- No `record.json` under the source dir → the server exits 2 (`no runs ...`).
- Cleanup: kill the server PID (Ctrl-C if foreground); temp conversion space
  removes itself.
