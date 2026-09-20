import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";

import { GameRecordSchema } from "../vendor/OpenFrontIO/src/core/Schemas";

// Observer-side converter: replay tape (record.json) -> archived GameRecord.
// Mirrors production createPartialGameRecord: empty turns are dropped, the
// players list holds humans only (replays re-derive nations from config),
// singleplayer needs no wire blanking. Exits non-zero with schema issues.
const HUMAN_CLIENT_ID = "ENGINECL";

const SOLO_DEFAULT_CONFIG = {
  gameMap: "Europe",
  gameMapSize: "Normal",
  gameMode: "Free For All",
  gameType: "Singleplayer",
  difficulty: "Easy",
  nations: 52,
  donateGold: false,
  donateTroops: false,
  bots: 400,
  infiniteGold: false,
  infiniteTroops: false,
  instantBuild: false,
  randomSpawn: false,
};

function main(): void {
  const runDir = process.argv[2];
  if (!runDir) {
    console.error("usage: build_game_record.ts <run-dir>");
    process.exit(2);
  }
  const tape = JSON.parse(readFileSync(path.join(runDir, "record.json"), "utf-8"));
  let end = Date.now();
  try {
    const result = JSON.parse(
      readFileSync(path.join(runDir, "live_result.json"), "utf-8"),
    );
    if (typeof result?.summary?.wall_ms === "number") {
      end = (tape.startedAt ?? end) + result.summary.wall_ms;
    }
  } catch {
    // Live result optional (engine-level tests have none).
  }
  const human = (tape.players ?? []).find(
    (p: { kind: string }) => p.kind === "human",
  );
  if (!human) {
    console.error("tape has no human player");
    process.exit(2);
  }
  const start = tape.startedAt ?? end;
  // Native keep rule (createPartialGameRecord): turns with intents OR a
  // state hash survive. Hash-only turns are the replay tripwire — the
  // client verifies them and raises desync on skew instead of silently
  // simulating the wrong world.
  const turns = (tape.turns ?? []).filter(
    (t: { intents: unknown[]; hash?: unknown }) =>
      t.intents.length > 0 || t.hash !== undefined,
  );
  const record = {
    info: {
      gameID: tape.gameId,
      lobbyCreatedAt: start,
      config: tape.gameConfig ?? SOLO_DEFAULT_CONFIG,
      players: [
        {
          clientID: HUMAN_CLIENT_ID,
          username: human.name,
          clanTag: null,
          persistentID: null,
          stats: {},
        },
      ],
      start,
      end,
      duration: Math.max(0, Math.floor((end - start) / 1000)),
      num_turns: tape.turns?.length ?? 0,
      lobbyFillTime: 0,
    },
    version: "v0.0.2",
    // Locally built shells report DEV; the replay shell accepts DEV records
    // from any build (see JoinLobbyModal.checkArchivedGame).
    gitCommit: "DEV",
    turns,
  };
  const parsed = GameRecordSchema.safeParse(record);
  if (!parsed.success) {
    console.error(JSON.stringify(parsed.error.issues.slice(0, 10), null, 2));
    process.exit(1);
  }
  const out = path.join(runDir, "game_record.json");
  writeFileSync(out, JSON.stringify(parsed.data));
  console.log(
    `game_record.json: ${turns.length} non-empty turns of ${tape.turns?.length ?? 0}, tick ${tape.ticks}`,
  );
}

main();
