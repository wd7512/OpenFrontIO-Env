import { readFile } from "node:fs/promises";
import path from "node:path";

import { createGameRunner } from "../vendor/OpenFrontIO/src/core/GameRunner";
import {
  GameMapLoader,
  MapData,
} from "../vendor/OpenFrontIO/src/core/game/GameMapLoader";
import { GameMapType } from "../vendor/OpenFrontIO/src/core/game/Maps.gen";

// Probe: boot the REAL client path (createGameRunner, the same function the
// browser worker uses) from a game_record.json, feed all turns, report
// whether spawn lands. Diagnoses replay stalls outside the browser.
function loaderFor(mapDir: string): GameMapLoader {
  const bin = (name: string) => async () =>
    new Uint8Array(await readFile(path.join(mapDir, name)));
  const data: MapData = {
    mapBin: bin("map.bin"),
    map4xBin: bin("map4x.bin"),
    map16xBin: async () => {
      try {
        return await bin("map16x.bin")();
      } catch {
        return await bin("map4x.bin")();
      }
    },
    manifest: async () => {
      const raw = JSON.parse(
        await readFile(path.join(mapDir, "manifest.json"), "utf8"),
      );
      // Mirror TerrainMapLoader: absent additionalNations defaults to [].
      if (raw.additionalNations === undefined) raw.additionalNations = [];
      return raw;
    },
    webpPath: "",
    layerPng: async () => null as never,
  };
  return { getMapData: (_map: GameMapType) => data };
}

async function main(): Promise<void> {
  const runDir = process.argv[2];
  const record = JSON.parse(
    await readFile(path.join(runDir, "game_record.json"), "utf-8"),
  );
  const tape = JSON.parse(await readFile(path.join(runDir, "record.json"), "utf-8"));
  const info = {
    gameID: record.info.gameID,
    lobbyCreatedAt: record.info.start,
    config: tape.gameConfig ?? record.info.config,
    players: record.info.players.map(
      (p: { username: string; clientID: string }) => ({
        username: p.username,
        clientID: p.clientID,
        clanTag: null,
      }),
    ),
  };
  const gr = await createGameRunner(info as never, "ENGINECL", loaderFor(tape.mapDir), () => {});
  // GameRunner consumes turns positionally (currTurn index), so gap-fill
  // sparse tapes exactly like decompressGameRecord does client-side.
  const sparse = record.turns as { turnNumber: number; intents: unknown[] }[];
  let last = -1;
  for (const turn of sparse) {
    while (last < turn.turnNumber - 1) {
      last++;
      gr.addTurn({ turnNumber: last, intents: [] } as never);
    }
    gr.addTurn(turn as never);
    last = turn.turnNumber;
  }
  const totalTurns = record.info.num_turns as number;
  while (last < totalTurns - 1) {
    last++;
    gr.addTurn({ turnNumber: last, intents: [] } as never);
  }
  let executed = 0;
  while (gr.executeNextTick() && executed < 10000) {
    executed++;
  }
  const game = gr.game;
  const human = game.players().find((p) => p.clientID() === "ENGINECL");
  console.log(
    JSON.stringify({
      executed,
      ticks: game.ticks(),
      inSpawnPhase: game.inSpawnPhase(),
      humanTiles: human?.numTilesOwned() ?? null,
      humanTroops: human?.troops() ?? null,
    }),
  );
}

main();
