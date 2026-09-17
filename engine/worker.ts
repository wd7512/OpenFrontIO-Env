import "./console-to-stderr";

import { readFile } from "node:fs/promises";
import path from "node:path";
import { createInterface } from "node:readline";

import { Config } from "../vendor/OpenFrontIO/src/core/configuration/Config";
import { Executor } from "../vendor/OpenFrontIO/src/core/execution/ExecutionManager";
import { WinCheckExecution } from "../vendor/OpenFrontIO/src/core/execution/WinCheckExecution";
import {
  Difficulty,
  Game,
  GameMapSize,
  GameMapType,
  GameMode,
  GameType,
  Nation,
  PlayerInfo,
  PlayerType,
} from "../vendor/OpenFrontIO/src/core/game/Game";
import { createGame } from "../vendor/OpenFrontIO/src/core/game/GameImpl";
import { createNationsForGame } from "../vendor/OpenFrontIO/src/core/game/NationCreation";
import {
  genTerrainFromBin,
  MapManifest,
} from "../vendor/OpenFrontIO/src/core/game/TerrainMapLoader";
import { PseudoRandom } from "../vendor/OpenFrontIO/src/core/PseudoRandom";
import { simpleHash } from "../vendor/OpenFrontIO/src/core/Util";
import {
  GameConfig,
  GameStartInfo,
  StampedIntent,
} from "../vendor/OpenFrontIO/src/core/Schemas";

const GAME_ID = "ENGINE01";
const CLIENT_ID = "ENGINECL";
const PLAYER_ID = "engine-smoke-human";
const PLAYER_NAME = "Smoke";
const MAX_ADVANCE = 100_000;
const MAX_SPAWN_TICKS = 10;
const MAX_NATIONS = 16;
const MAX_ATTACK_TROOPS = 1_000_000;

const DIFFICULTIES: Record<string, Difficulty> = {
  easy: Difficulty.Easy,
  medium: Difficulty.Medium,
  hard: Difficulty.Hard,
  impossible: Difficulty.Impossible,
};

interface NationState {
  id: string;
  name: string;
  type: string;
  troops: number;
  gold: string;
  tiles: number;
  alive: boolean;
}

interface AttackState {
  id: string;
  attacker: string;
  target: string | null;
  troops: number;
  retreating: boolean;
}

interface Snapshot {
  status: string;
  gameId: string;
  tick: number;
  inSpawnPhase: boolean;
  width: number;
  height: number;
  winner: string | null;
  attacks: AttackState[];
  nations: NationState[];
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
  private executor: Executor | null = null;
  private nationIDs: string[] = [];

  async start(
    mapDir: string,
    spawnX: number,
    spawnY: number,
    nations: number = 0,
    difficulty: string = "easy",
  ): Promise<Snapshot> {
    if (this.game !== null) {
      throw new Error("engine already started");
    }
    if (
      typeof nations !== "number" ||
      !Number.isInteger(nations) ||
      nations < 0 ||
      nations > MAX_NATIONS
    ) {
      throw new Error(
        `invalid nations: expected an integer in [0, ${MAX_NATIONS}], got ${nations}`,
      );
    }
    const difficultyValue = DIFFICULTIES[difficulty];
    if (difficultyValue === undefined) {
      throw new Error(
        `invalid difficulty: expected one of easy/medium/hard/impossible, got ${difficulty}`,
      );
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
      difficulty: difficultyValue,
      nations: nations > 0 ? nations : "disabled",
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
    // Production nation creation: random picks from the manifest nations,
    // procedurally generated names beyond that (spawn cells undefined, so
    // SpawnExecution places them randomly — the HumansVsNations path).
    const nationObjs: Nation[] =
      nations > 0
        ? createNationsForGame(
            { config: gameConfig } as GameStartInfo,
            manifest.nations ?? [],
            manifest.additionalNations ?? [],
            humans.length,
            new PseudoRandom(simpleHash(GAME_ID)),
          )
        : [];
    const game = createGame(humans, nationObjs, gameMap, miniGameMap, config);
    const executor = new Executor(game, GAME_ID, CLIENT_ID, []);
    if (nationObjs.length > 0) {
      game.addExecution(...executor.nationExecutions());
    }
    game.addExecution(new WinCheckExecution());

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
    // intent never lands, hence the guard.) Nations queue their own
    // SpawnExecution during the phase but only land after it, so keep driving
    // until every nation has spawned too.
    this.nationIDs = nationObjs.map((n) => n.playerInfo.id);
    let guard = 0;
    while (
      (game.inSpawnPhase() || !this.allSpawned(game)) &&
      guard < MAX_SPAWN_TICKS
    ) {
      game.executeNextTick();
      guard++;
    }
    if (game.inSpawnPhase()) {
      throw new Error("spawn phase did not end after the spawn intent");
    }
    if (!this.allSpawned(game)) {
      throw new Error("not all nations spawned after the spawn phase");
    }

    this.game = game;
    this.executor = executor;
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

  attack(target: unknown, troops: unknown): Snapshot {
    const game = this.requireGame();
    const executor = this.requireExecutor();
    // "expand" conquers adjacent neutral land (production path: an attack
    // intent with a null targetID resolves to TerraNullius — this is how
    // live clients expand). "nation-N" targets a nation player.
    let targetID: string | null;
    if (target === "expand") {
      targetID = null;
    } else if (typeof target === "string" && /^nation-\d+$/.test(target)) {
      const index = Number.parseInt(target.slice("nation-".length), 10) - 1;
      if (index < 0 || index >= this.nationIDs.length) {
        throw new Error(
          `invalid attack target: no such nation ${JSON.stringify(target)}`,
        );
      }
      targetID = this.nationIDs[index];
    } else {
      throw new Error(
        `invalid attack target: expected "expand" or "nation-N", got ${JSON.stringify(target)}`,
      );
    }
    if (
      typeof troops !== "number" ||
      !Number.isInteger(troops) ||
      troops <= 0 ||
      troops > MAX_ATTACK_TROOPS
    ) {
      throw new Error(
        `invalid attack troops: expected an integer in [1, ${MAX_ATTACK_TROOPS}], got ${JSON.stringify(troops)}`,
      );
    }
    // Production intent path, the same one live turns take through
    // Executor.createExec: the stamped intent becomes an AttackExecution.
    const attackIntent = {
      type: "attack",
      clientID: CLIENT_ID,
      targetID,
      troops,
    } as StampedIntent;
    game.addExecution(executor.createExec(attackIntent));
    return this.snapshot("ok");
  }

  private requireGame(): Game {
    if (this.game === null) {
      throw new Error("engine not started");
    }
    return this.game;
  }

  private requireExecutor(): Executor {
    if (this.executor === null) {
      throw new Error("engine not started");
    }
    return this.executor;
  }

  private allSpawned(game: Game): boolean {
    return this.nationIDs.every(
      (id) => game.hasPlayer(id) && game.player(id).hasSpawned(),
    );
  }

  private snapshot(status: string): Snapshot {
    const game = this.requireGame();
    const player = game.player(PLAYER_ID);
    const spawnTile = player.spawnTile();
    const winner = game.getWinner();
    const winnerName =
      winner === null
        ? null
        : typeof winner === "string"
          ? winner
          : typeof (winner as { name?: unknown }).name === "function"
            ? (winner as { name: () => string }).name()
            : null;
    return {
      status,
      gameId: GAME_ID,
      tick: game.ticks(),
      inSpawnPhase: game.inSpawnPhase(),
      width: game.width(),
      height: game.height(),
      winner: winnerName,
      attacks: player.outgoingAttacks().map((attack) => {
        const target = attack.target() as unknown as {
          isPlayer?: () => boolean;
          name?: () => string;
        };
        return {
          id: attack.id(),
          attacker: attack.attacker().name(),
          target:
            typeof target.isPlayer === "function" && !target.isPlayer()
              ? "terra-nullius"
              : typeof target.name !== "function"
                ? null
                : target.name(),
          troops: attack.troops(),
          retreating: attack.retreating(),
        };
      }),
      nations: this.nationIDs.map((id) => {
        const nation = game.player(id);
        return {
          id: nation.id(),
          name: nation.name(),
          type: "nation",
          troops: nation.troops(),
          gold: nation.gold().toString(),
          tiles: nation.numTilesOwned(),
          alive: nation.isAlive(),
        };
      }),
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
  nations?: number;
  difficulty?: string;
  ticks?: number;
  target?: unknown;
  troops?: unknown;
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
          request.nations ?? 0,
          request.difficulty ?? "easy",
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
      case "attack":
        writeResponse({
          id,
          ok: true,
          result: session.attack(request.target, request.troops),
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
