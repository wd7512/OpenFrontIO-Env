import "./console-to-stderr";

import { readFile } from "node:fs/promises";
import path from "node:path";
import { createInterface } from "node:readline";

import { Config } from "../vendor/OpenFrontIO/src/core/configuration/Config";
import { Executor } from "../vendor/OpenFrontIO/src/core/execution/ExecutionManager";
import {
  Difficulty,
  Game,
  GameMapSize,
  GameMapType,
  GameMode,
  GameType,
  PlayerInfo,
  PlayerType,
} from "../vendor/OpenFrontIO/src/core/game/Game";
import { createGame } from "../vendor/OpenFrontIO/src/core/game/GameImpl";
import {
  genTerrainFromBin,
  MapManifest,
} from "../vendor/OpenFrontIO/src/core/game/TerrainMapLoader";
import {
  GameConfig,
  StampedIntent,
} from "../vendor/OpenFrontIO/src/core/Schemas";

const GAME_ID = "ENGINE01";
const CLIENT_ID = "ENGINECL";
const PLAYER_ID = "engine-smoke-human";
const PLAYER_NAME = "Smoke";
const MAX_ADVANCE = 100_000;
const MAX_SPAWN_TICKS = 10;

interface Snapshot {
  status: string;
  gameId: string;
  tick: number;
  inSpawnPhase: boolean;
  width: number;
  height: number;
  human: {
    id: string;
    name: string;
    smallID: number;
    troops: number;
    gold: string;
    tiles: number;
    spawnTile: { x: number; y: number } | null;
    hash: number;
  };
}

class EngineSession {
  private game: Game | null = null;

  async start(mapDir: string, spawnX: number, spawnY: number): Promise<Snapshot> {
    if (this.game !== null) {
      throw new Error("engine already started");
    }

    const manifest = JSON.parse(
      await readFile(path.join(mapDir, "manifest.json"), "utf8"),
    ) as MapManifest;
    const mapBin = new Uint8Array(await readFile(path.join(mapDir, "map.bin")));
    const map4xBin = new Uint8Array(
      await readFile(path.join(mapDir, "map4x.bin")),
    );

    const gameMap = await genTerrainFromBin(manifest.map, mapBin);
    const miniGameMap = await genTerrainFromBin(manifest.map4x, map4xBin);

    // Same required GameConfig fields production fills; no defaults are applied
    // because Config reads the object directly. startingGold is intentionally
    // left unset to match the production schema default (0n).
    const gameConfig = {
      gameMap: GameMapType.Asia,
      gameMapSize: GameMapSize.Normal,
      gameMode: GameMode.FFA,
      gameType: GameType.Singleplayer,
      difficulty: Difficulty.Medium,
      nations: "disabled",
      donateGold: false,
      donateTroops: false,
      bots: 0,
      infiniteGold: false,
      infiniteTroops: false,
      instantBuild: false,
      randomSpawn: false,
    } as GameConfig;

    const config = new Config(gameConfig, null, false);
    const humans = [
      new PlayerInfo(PLAYER_NAME, PlayerType.Human, CLIENT_ID, PLAYER_ID),
    ];
    const game = createGame(humans, [], gameMap, miniGameMap, config);
    const executor = new Executor(game, GAME_ID, CLIENT_ID, []);

    // Production intent path: Executor builds the SpawnExecution the same way a
    // live turn would. Singleplayer + Human makes the spawn end the spawn phase,
    // and SpawnExecution itself queues the production PlayerExecution.
    const spawnIntent = {
      type: "spawn",
      clientID: CLIENT_ID,
      tile: game.ref(spawnX, spawnY),
    } as StampedIntent;
    game.addExecution(executor.createExec(spawnIntent));

    // GameImpl double-buffers executions: a newly added execution is init()ed at
    // the tail of one tick and only tick()s on the next. So drive the real
    // production loop until the spawn phase actually ends rather than guessing a
    // tick count. (Singleplayer blocks forever on inSpawnPhase if the spawn
    // intent never lands, hence the guard.)
    let guard = 0;
    while (game.inSpawnPhase() && guard < MAX_SPAWN_TICKS) {
      game.executeNextTick();
      guard++;
    }
    if (game.inSpawnPhase()) {
      throw new Error("spawn phase did not end after the spawn intent");
    }

    this.game = game;
    return this.snapshot("started");
  }

  query(): Snapshot {
    return this.snapshot("ok");
  }

  advance(ticks: number): Snapshot {
    if (!Number.isInteger(ticks) || ticks <= 0 || ticks > MAX_ADVANCE) {
      throw new Error(
        `invalid advance: expected an integer in [1, ${MAX_ADVANCE}], got ${ticks}`,
      );
    }
    const game = this.requireGame();
    for (let i = 0; i < ticks; i++) {
      game.executeNextTick();
    }
    return this.snapshot("ok");
  }

  private requireGame(): Game {
    if (this.game === null) {
      throw new Error("engine not started");
    }
    return this.game;
  }

  private snapshot(status: string): Snapshot {
    const game = this.requireGame();
    const player = game.player(PLAYER_ID);
    const spawnTile = player.spawnTile();
    return {
      status,
      gameId: GAME_ID,
      tick: game.ticks(),
      inSpawnPhase: game.inSpawnPhase(),
      width: game.width(),
      height: game.height(),
      human: {
        id: player.id(),
        name: player.name(),
        smallID: player.smallID(),
        troops: player.troops(),
        gold: player.gold().toString(),
        tiles: player.numTilesOwned(),
        spawnTile:
          spawnTile === undefined
            ? null
            : { x: game.x(spawnTile), y: game.y(spawnTile) },
        hash: player.hash(),
      },
    };
  }
}

interface Request {
  id?: number | string;
  cmd?: string;
  mapDir?: string;
  spawnX?: number;
  spawnY?: number;
  ticks?: number;
}

const session = new EngineSession();

function writeResponse(payload: Record<string, unknown>): void {
  process.stdout.write(JSON.stringify(payload) + "\n");
}

async function handle(raw: string): Promise<boolean> {
  let request: Request;
  try {
    request = JSON.parse(raw) as Request;
  } catch {
    writeResponse({ ok: false, error: "invalid JSON request" });
    return true;
  }

  const id = request.id ?? null;
  try {
    switch (request.cmd) {
      case "start": {
        if (typeof request.mapDir !== "string") {
          throw new Error("start requires mapDir");
        }
        const result = await session.start(
          request.mapDir,
          request.spawnX ?? 50,
          request.spawnY ?? 50,
        );
        writeResponse({ id, ok: true, result });
        return true;
      }
      case "query":
        writeResponse({ id, ok: true, result: session.query() });
        return true;
      case "advance":
        writeResponse({
          id,
          ok: true,
          result: session.advance(request.ticks as number),
        });
        return true;
      case "close":
        writeResponse({ id, ok: true, result: { status: "closed" } });
        return false;
      default:
        throw new Error(`unknown command: ${String(request.cmd)}`);
    }
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : String(error);
    process.stderr.write(`engine error: ${message}\n`);
    writeResponse({ id, ok: false, error: message });
    return true;
  }
}

const rl = createInterface({ input: process.stdin });
let chain: Promise<void> = Promise.resolve();
let closing = false;

rl.on("line", (line: string) => {
  if (line.trim() === "") return;
  chain = chain.then(async () => {
    if (closing) return;
    const keepOpen = await handle(line);
    if (!keepOpen) {
      closing = true;
      rl.close();
      process.exit(0);
    }
  });
});

rl.on("close", () => {
  if (!closing) {
    process.exit(0);
  }
});
