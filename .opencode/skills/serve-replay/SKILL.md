---
name: serve-replay
description: Use when the user wants to watch a finished game replay, serve a run in the real game client, or view a match through the engine replay.
---

# Serve Replay

Serve a finished run through the real engine replay (`createGameRunner`, the browser worker path) in the actual game client, without writing anything into the run dir.

## Steps

1. Pick the run dir under `raw/` (canonical home for experiment data; latest `openfront-cycle-*` unless told otherwise). Done when: it holds `record.json` + `live_result.json`.
2. Bundle the converter with an **absolute** resources alias (relative alias fails to resolve), run it on the run dir, then move the record out to `/tmp` staging. Done when: the run dir is byte-identical and staging holds `game_record.json`.
   ```bash
   engine/node_modules/.bin/esbuild scripts/build_game_record.ts --bundle --platform=node --format=esm --alias:resources=$PWD/vendor/OpenFrontIO/resources --outfile=/tmp/replay/build_game_record.mjs
   node /tmp/replay/build_game_record.mjs <run-dir>   # validates against production GameRecordSchema
   mv <run-dir>/game_record.json /tmp/replay-view/game_record.json
   ```
3. Start the archive stub (unmodified repo script) on 8787 in the background. Done when: `curl http://127.0.0.1:8787/game/<gameID>` returns 200 with matching `gameID`.
   ```bash
   nohup uv run python scripts/serve_archive.py /tmp/replay-view 8787 > /tmp/replay-view/archive.log 2>&1 &
   ```
4. Start the vendor client (`vendor/OpenFrontIO`, `npm run start:client`, serves :9000) in the background. Done when: `:9000` returns 200.
5. View: open `http://localhost:9000`, join the private lobby with `<gameID>` (`ENGINE01` for engine runs). No live lobby exists, so the client falls through to `checkArchivedGame` and replays the full tape in the real renderer.

## Reference

- No client config needed: `getApiBase()` on localhost defaults to `http://localhost:8787`.
- `gameID` must match `GAME_ID_REGEX` (`^[A-Za-z0-9]{8}$`); read it from `record.json`'s `gameId`.
- `ws proxy ECONNREFUSED` in the client log is harmless (no multiplayer server); `checkActiveLobby` returns false and the archive path runs.
- Cleanup: kill both PIDs, `rm -rf /tmp/replay /tmp/replay-view`.
