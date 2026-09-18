import "./console-to-stderr";

import { writeFileSync } from "node:fs";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { createInterface } from "node:readline";

import { Config } from "../vendor/OpenFrontIO/src/core/configuration/Config";
import { DoomsdayClockExecution } from "../vendor/OpenFrontIO/src/core/execution/DoomsdayClockExecution";
import { Executor } from "../vendor/OpenFrontIO/src/core/execution/ExecutionManager";
import { RecomputeRailClusterExecution } from "../vendor/OpenFrontIO/src/core/execution/RecomputeRailClusterExecution";
import { WinCheckExecution } from "../vendor/OpenFrontIO/src/core/execution/WinCheckExecution";
import {
  Difficulty,
  Game,
  GameMapSize,
  GameMapType,
  GameMode,
  GameType,
  Nation,
  Player,
  PlayerInfo,
  PlayerType,
  UnitType,
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
const PLAYER_ID = "engine-agent-human";
const PLAYER_NAME = "Agent";
const MAX_ADVANCE = 100_000;
const MAX_SPAWN_TICKS = 10;
const MAX_NATIONS = 100;
const MAX_ATTACK_TROOPS = 1_000_000;
const MAX_SPAWN_ATTEMPTS = 10_000;
const MAX_TRIBES = 500;

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
  immune: boolean;
  borders_human: boolean;
}

interface AttackState {
  id: string;
  attacker: string;
  target: string | null;
  troops: number;
  retreating: boolean;
}

interface TribeState {
  id: string;
  name: string;
  type: "tribe";
  troops: number;
  tiles: number;
  alive: boolean;
  borders_human: boolean;
}

interface BoatState {
  id: string;
  troops: number;
}

interface BoatTargetState {
  x: number;
  y: number;
  owner: string;
  troops: number | null;
  tiles: number | null;
}

interface UnitState {
  id: string;
  type: string;
  level: number;
  x: number;
  y: number;
  troops: number;
  under_construction: boolean;
}

interface AllianceState {
  id: string;
  name: string;
}

interface EmbargoState {
  id: string;
  name: string;
}

// Human build-menu parity: the PlayerBuildable set (BuildMenus structures +
// buildable attacks + transport ships, which already have their own tools).
const BUILDABLE: Record<string, UnitType> = {
  city: UnitType.City,
  "defense-post": UnitType.DefensePost,
  "sam-launcher": UnitType.SAMLauncher,
  "missile-silo": UnitType.MissileSilo,
  port: UnitType.Port,
  factory: UnitType.Factory,
  "atom-bomb": UnitType.AtomBomb,
  "hydrogen-bomb": UnitType.HydrogenBomb,
  mirv: UnitType.MIRV,
  warship: UnitType.Warship,
};

interface Snapshot {
  status: string;
  gameId: string;
  tick: number;
  inSpawnPhase: boolean;
  width: number;
  height: number;
  winner: string | null;
  tribes: number;
  tribe_list: TribeState[];
  boats: BoatState[];
  boat_targets: BoatTargetState[];
  units: UnitState[];
  alliances: AllianceState[];
  alliance_requests: { incoming: string[]; outgoing: string[] };
  embargoes: EmbargoState[];
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
  private tribeIDs: string[] = [];
  // Human player id, drawn from the seeded RNG at boot exactly like
  // GameRunner (humans first, then nations): identical ids and identical
  // downstream RNG stream, so tapes replay bit-for-bit in the real client.
  private humanID: string = PLAYER_ID;
  // Replay tape: every stamped human intent, bucketed per executed game
  // tick exactly like the production server archives turns. Observer-only:
  // recording never adds, alters, or delays an intent.
  private pendingIntents: StampedIntent[] = [];
  private turns: { turnNumber: number; intents: StampedIntent[] }[] = [];
  private mapDir: string = "";
  private recordStartedAt: number = 0;
  private recordConfig: Record<string, unknown> = {};

  private submit(intent: StampedIntent): void {
    const game = this.requireGame();
    const executor = this.requireExecutor();
    this.pendingIntents.push({ ...intent });
    game.addExecution(executor.createExec(intent));
  }

  private recordTick(): void {
    const intents = this.pendingIntents;
    this.pendingIntents = [];
    this.turns.push({ turnNumber: this.turns.length, intents });
  }

  async start(
    mapDir: string,
    spawnX: number | null,
    spawnY: number | null,
    nations: number = 0,
    difficulty: string = "easy",
    mapSize: string = "full",
    tribes: number = 0,
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
    if (
      typeof tribes !== "number" ||
      !Number.isInteger(tribes) ||
      tribes < 0 ||
      tribes > MAX_TRIBES
    ) {
      throw new Error(
        `invalid tribes: expected an integer in [0, ${MAX_TRIBES}], got ${tribes}`,
      );
    }

    const manifest = JSON.parse(
      await readFile(path.join(mapDir, "manifest.json"), "utf8"),
    ) as MapManifest;
    // Production resolution rule (TerrainMapLoader.loadTerrainMap): Normal
    // plays full-res; Compact plays map4x with manifest/additional nation
    // coordinates halved. "full" keeps the fixture behavior (map.bin +
    // map4x mini) for fast unit tests; "compact" is the real online small.
    if (mapSize !== "full" && mapSize !== "compact") {
      throw new Error(
        `invalid mapSize: expected "full" or "compact", got ${JSON.stringify(mapSize)}`,
      );
    }
    const compact = mapSize === "compact";
    if (compact) {
      for (const nation of manifest.nations ?? []) {
        if (nation.coordinates !== undefined) {
          nation.coordinates = [
            Math.floor(nation.coordinates[0] / 2),
            Math.floor(nation.coordinates[1] / 2),
          ];
        }
      }
      for (const nation of manifest.additionalNations ?? []) {
        if (nation.coordinates !== undefined) {
          nation.coordinates = [
            Math.floor(nation.coordinates[0] / 2),
            Math.floor(nation.coordinates[1] / 2),
          ];
        }
      }
    }
    const mainMeta = compact ? manifest.map4x : manifest.map;
    const mainBinName = compact ? "map4x.bin" : "map.bin";
    const miniMeta = compact ? manifest.map16x : manifest.map4x;
    const miniBinName = compact ? "map16x.bin" : "map4x.bin";
    const mapBin = new Uint8Array(await readFile(path.join(mapDir, mainBinName)));
    const map4xBin = new Uint8Array(await readFile(path.join(mapDir, miniBinName)));

    const gameMap = await genTerrainFromBin(mainMeta, mapBin);
    const miniGameMap = await genTerrainFromBin(miniMeta, map4xBin);

    // Human spawn: explicit tile, or seeded random land when null (real maps
    // have no single safe coordinate — (50,50) is ocean on Britannia).
    let spawnTileX = spawnX;
    let spawnTileY = spawnY;
    if (spawnTileX === null || spawnTileY === null) {
      const rng = new PseudoRandom(simpleHash(`${GAME_ID}:spawn`));
      let placed = false;
      for (let attempt = 0; attempt < MAX_SPAWN_ATTEMPTS; attempt++) {
        const x = rng.nextInt(0, gameMap.width());
        const y = rng.nextInt(0, gameMap.height());
        if (gameMap.isLand(gameMap.ref(x, y))) {
          spawnTileX = x;
          spawnTileY = y;
          placed = true;
          break;
        }
      }
      if (!placed) {
        throw new Error("could not find a land spawn tile");
      }
    }

    // Same required GameConfig fields production fills; no defaults are applied
    // because Config reads the object directly. startingGold is intentionally
    // left unset to match the production schema default (0n).
    const gameConfig = {
      gameMap:
        (GameMapType as unknown as Record<string, GameMapType>)[
          manifest.name
        ] ?? GameMapType.Asia,
      gameMapSize: compact ? GameMapSize.Compact : GameMapSize.Normal,
      gameMode: GameMode.FFA,
      gameType: GameType.Singleplayer,
      difficulty: difficultyValue,
      nations: nations > 0 ? nations : "disabled",
      donateGold: false,
      donateTroops: false,
      bots: tribes,
      infiniteGold: false,
      infiniteTroops: false,
      instantBuild: false,
      randomSpawn: false,
    } as GameConfig;

    const config = new Config(gameConfig, null, false);
    this.recordConfig = { ...gameConfig };
    this.recordStartedAt = Date.now();
    // Mirror GameRunner.createGameRunner exactly: one seeded RNG, humans
    // first (their ids consume the first draws), then nations. Any other
    // order splits the RNG stream and tapes stop replaying.
    const random = new PseudoRandom(simpleHash(GAME_ID));
    const humans = [
      new PlayerInfo(
        PLAYER_NAME,
        PlayerType.Human,
        CLIENT_ID,
        random.nextID(),
        false,
        null,
        [],
        null,
      ),
    ];
    this.humanID = humans[0].id;
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
            random,
          )
        : [];
    const game = createGame(humans, nationObjs, gameMap, miniGameMap, config);
    const executor = new Executor(game, GAME_ID, CLIENT_ID, []);
    // Mirror GameRunner.init execution order and conditions.
    if (game.config().spawnNations()) {
      game.addExecution(...executor.nationExecutions());
    }
    if (game.config().bots() > 0) {
      game.addExecution(...executor.spawnTribes(game.config().bots()));
    }
    game.addExecution(new WinCheckExecution());
    if (game.config().doomsdayClockConfig().enabled) {
      game.addExecution(new DoomsdayClockExecution());
    }
    if (!game.config().isUnitDisabled(UnitType.Factory)) {
      game.addExecution(new RecomputeRailClusterExecution(game.railNetwork()));
    }

    // Production intent path: Executor builds the SpawnExecution the same way a
    // live turn would. Singleplayer + Human makes the spawn end the spawn phase,
    // and SpawnExecution itself queues the production PlayerExecution.
    const spawnIntent = {
      type: "spawn",
      clientID: CLIENT_ID,
      tile: game.ref(spawnTileX as number, spawnTileY as number),
    } as StampedIntent;
    // start() runs before this.game is stored, so submit() (which needs the
    // stored handle) cannot be used here: tape the intent and add it direct.
    this.pendingIntents = [];
    this.turns = [];
    this.pendingIntents.push({ ...spawnIntent });
    game.addExecution(executor.createExec(spawnIntent));
    // GameImpl double-buffers executions: a newly added execution is init()ed at
    // the tail of one tick and only tick()s on the next. So drive the real
    // production loop until the spawn phase actually ends rather than guessing a
    // tick count. (Singleplayer blocks forever on inSpawnPhase if the spawn
    // intent never lands, hence the guard.) Nations queue their own
    // SpawnExecution during the phase but only land after it, so keep driving
    // until every nation has spawned too.
    this.nationIDs = nationObjs.map((n) => n.playerInfo.id);
    this.mapDir = mapDir;
    let guard = 0;
    while (
      (game.inSpawnPhase() || !this.allSpawned(game)) &&
      guard < MAX_SPAWN_TICKS
    ) {
      game.executeNextTick();
      this.recordTick();
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
    this.tribeIDs = [];
    this.refreshTribeIDs(game);
    return this.snapshot("started");
  }

  query(): Snapshot {
    return this.snapshot("ok");
  }

  saveRecord(): {
    gameId: string;
    mapDir: string;
    ticks: number;
    startedAt: number;
    gameConfig: Record<string, unknown>;
    players: { id: string; name: string; kind: string }[];
    turns: { turnNumber: number; intents: StampedIntent[] }[];
    path: string | null;
  } {
    const game = this.requireGame();
    const players: { id: string; name: string; kind: string }[] = [];
    const human = game.player(this.humanID);
    players.push({ id: this.humanID, name: human.name(), kind: "human" });
    for (const id of this.nationIDs) {
      players.push({
        id,
        name: game.hasPlayer(id) ? game.player(id).name() : id,
        kind: "nation",
      });
    }
    for (const p of game.players()) {
      if (p.id() === this.humanID || this.nationIDs.includes(p.id())) continue;
      players.push({ id: p.id(), name: p.name(), kind: "tribe" });
    }
    const record = {
      gameId: GAME_ID,
      mapDir: this.mapDir,
      ticks: game.ticks(),
      startedAt: this.recordStartedAt,
      gameConfig: this.recordConfig,
      players,
      turns: this.turns,
    };
    const dir = process.env.OPENFRONT_RECORD_DIR;
    let recordPath: string | null = null;
    if (dir) {
      recordPath = path.join(dir, "record.json");
      writeFileSync(recordPath, JSON.stringify(record));
    }
    return { ...record, path: recordPath };
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
      this.recordTick();
    }
    return this.snapshot("ok");
  }

  private collectTribeIDs(game: Game): string[] {
    // Tribe players are Bot type; nations and the human are excluded by type.
    // Sorted for stable tribe-N numbering across snapshots.
    return game
      .players()
      .filter((p) => p.type() === PlayerType.Bot)
      .map((p) => p.id())
      .sort();
  }

  private refreshTribeIDs(game: Game): void {
    // Tribes can spawn late and die mid-game. Numbers stay stable: the initial
    // population is sorted, late newcomers append at the end (never shifting
    // existing numbers), and the dead keep their slots (projected via the
    // hasPlayer guard, attacks on them reject).
    for (const id of this.collectTribeIDs(game)) {
      if (!this.tribeIDs.includes(id)) {
        this.tribeIDs.push(id);
      }
    }
  }

  attack(target: unknown, troops: unknown): Snapshot {
    const game = this.requireGame();
    const executor = this.requireExecutor();
    // "expand" conquers adjacent neutral land (production path: an attack
    // intent with a null targetID resolves to TerraNullius — this is how
    // live clients expand). "nation-N" targets a nation player, "tribe-N" a
    // neutral tribe player; both ride the same AttackExecution path.
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
    } else if (typeof target === "string" && /^tribe-\d+$/.test(target)) {
      const index = Number.parseInt(target.slice("tribe-".length), 10) - 1;
      if (index < 0 || index >= this.tribeIDs.length) {
        throw new Error(
          `invalid attack target: no such tribe ${JSON.stringify(target)}`,
        );
      }
      targetID = this.tribeIDs[index];
    } else {
      throw new Error(
        `invalid attack target: expected "expand", "nation-N" or "tribe-N", got ${JSON.stringify(target)}`,
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
    this.submit(attackIntent);
    return this.snapshot("ok");
  }

  cancelAttack(attackID: unknown): Snapshot {
    const game = this.requireGame();
    const executor = this.requireExecutor();
    // Production path: a cancel_attack intent becomes a RetreatExecution,
    // the same one a human retreat button press takes.
    const live = game.player(this.humanID).outgoingAttacks();
    if (typeof attackID !== "string" || !live.some((a) => a.id() === attackID)) {
      throw new Error(
        `invalid attack id: no such outgoing attack ${JSON.stringify(attackID)}`,
      );
    }
    const cancelIntent = {
      type: "cancel_attack",
      clientID: CLIENT_ID,
      attackID,
    } as StampedIntent;
    this.submit(cancelIntent);
    return this.snapshot("ok");
  }

  boatAttack(x: unknown, y: unknown, troops: unknown): Snapshot {
    const game = this.requireGame();
    const executor = this.requireExecutor();
    // Production path: a boat intent becomes a TransportShipExecution, the
    // same one a human boat-attack order takes. The engine itself validates
    // the destination tile; here we only check integer bounds.
    for (const [label, value, max] of [
      ["x", x, game.width()],
      ["y", y, game.height()],
    ] as const) {
      if (
        typeof value !== "number" ||
        !Number.isInteger(value) ||
        value < 0 ||
        value >= max
      ) {
        throw new Error(
          `invalid boat destination ${label}: expected an integer in [0, ${max}), got ${JSON.stringify(value)}`,
        );
      }
    }
    if (
      typeof troops !== "number" ||
      !Number.isInteger(troops) ||
      troops <= 0 ||
      troops > MAX_ATTACK_TROOPS
    ) {
      throw new Error(
        `invalid boat troops: expected an integer in [1, ${MAX_ATTACK_TROOPS}], got ${JSON.stringify(troops)}`,
      );
    }
    const boatIntent = {
      type: "boat",
      clientID: CLIENT_ID,
      dst: game.ref(x as number, y as number),
      troops,
    } as StampedIntent;
    this.submit(boatIntent);
    return this.snapshot("ok");
  }

  cancelBoat(unitID: unknown): Snapshot {
    const game = this.requireGame();
    const executor = this.requireExecutor();
    // Production path: a cancel_boat intent becomes a BoatRetreatExecution.
    // The schema wants a numeric unit id, so resolve the boat first.
    const boats = game.player(this.humanID).units([UnitType.TransportShip]);
    const wanted = String(unitID);
    const boat = boats.find((b) => String(b.id()) === wanted);
    if (
      (typeof unitID !== "string" && typeof unitID !== "number") ||
      boat === undefined
    ) {
      throw new Error(
        `invalid boat id: no such transport ship ${JSON.stringify(unitID)}`,
      );
    }
    const cancelIntent = {
      type: "cancel_boat",
      clientID: CLIENT_ID,
      unitID: boat.id(),
    } as StampedIntent;
    this.submit(cancelIntent);
    return this.snapshot("ok");
  }

  buildUnit(unit: unknown, x: unknown, y: unknown): Snapshot {
    const game = this.requireGame();
    const executor = this.requireExecutor();
    // Production path: a build_unit intent becomes a ConstructionExecution,
    // the same one a human build-menu click takes. Structures need owned
    // land, nukes take the target tile, warships need water access — the
    // engine validates all of it; here we check the menu allowlist and
    // integer bounds only.
    if (typeof unit !== "string" || !(unit in BUILDABLE)) {
      throw new Error(
        `invalid build unit: expected one of ${Object.keys(BUILDABLE).join(", ")}, got ${JSON.stringify(unit)}`,
      );
    }
    for (const [label, value, max] of [
      ["x", x, game.width()],
      ["y", y, game.height()],
    ] as const) {
      if (
        typeof value !== "number" ||
        !Number.isInteger(value) ||
        value < 0 ||
        value >= max
      ) {
        throw new Error(
          `invalid build ${label}: expected an integer in [0, ${max}), got ${JSON.stringify(value)}`,
        );
      }
    }
    const buildIntent = {
      type: "build_unit",
      clientID: CLIENT_ID,
      unit: BUILDABLE[unit],
      tile: game.ref(x as number, y as number),
    } as StampedIntent;
    this.submit(buildIntent);
    return this.snapshot("ok");
  }

  upgradeUnit(unitID: unknown): Snapshot {
    const game = this.requireGame();
    const executor = this.requireExecutor();
    // Production path: an upgrade_structure intent, same as the human
    // upgrade button. The numeric unit id resolves against live human units.
    const wanted = String(unitID);
    const target = game
      .player(this.humanID)
      .units()
      .find((u) => String(u.id()) === wanted);
    if (
      (typeof unitID !== "string" && typeof unitID !== "number") ||
      target === undefined
    ) {
      throw new Error(
        `invalid unit id: no such human unit ${JSON.stringify(unitID)}`,
      );
    }
    const upgradeIntent = {
      type: "upgrade_structure",
      clientID: CLIENT_ID,
      unit: target.type(),
      unitId: target.id(),
    } as StampedIntent;
    this.submit(upgradeIntent);
    return this.snapshot("ok");
  }

  deleteUnit(unitID: unknown): Snapshot {
    const game = this.requireGame();
    const executor = this.requireExecutor();
    // Production path: a delete_unit intent, same as the human delete button.
    const wanted = String(unitID);
    const target = game
      .player(this.humanID)
      .units()
      .find((u) => String(u.id()) === wanted);
    if (
      (typeof unitID !== "string" && typeof unitID !== "number") ||
      target === undefined
    ) {
      throw new Error(
        `invalid unit id: no such human unit ${JSON.stringify(unitID)}`,
      );
    }
    const deleteIntent = {
      type: "delete_unit",
      clientID: CLIENT_ID,
      unitId: target.id(),
    } as StampedIntent;
    this.submit(deleteIntent);
    return this.snapshot("ok");
  }

  private resolveDiploTarget(target: unknown): string {
    // Diplomacy addresses nations and tribes by their adapter labels; the
    // production intents take internal player ids (MappedID).
    const game = this.requireGame();
    this.refreshTribeIDs(game);
    if (typeof target === "string" && /^nation-\d+$/.test(target)) {
      const index = Number.parseInt(target.slice("nation-".length), 10) - 1;
      if (index < 0 || index >= this.nationIDs.length) {
        throw new Error(
          `invalid diplomacy target: no such nation ${JSON.stringify(target)}`,
        );
      }
      return this.nationIDs[index];
    }
    if (typeof target === "string" && /^tribe-\d+$/.test(target)) {
      const index = Number.parseInt(target.slice("tribe-".length), 10) - 1;
      if (index < 0 || index >= this.tribeIDs.length) {
        throw new Error(
          `invalid diplomacy target: no such tribe ${JSON.stringify(target)}`,
        );
      }
      return this.tribeIDs[index];
    }
    throw new Error(
      `invalid diplomacy target: expected "nation-N" or "tribe-N", got ${JSON.stringify(target)}`,
    );
  }

  private labelForPlayerID(id: string): string {
    const nation = this.nationIDs.indexOf(id);
    if (nation >= 0) return `nation-${nation + 1}`;
    const tribe = this.tribeIDs.indexOf(id);
    if (tribe >= 0) return `tribe-${tribe + 1}`;
    if (id === this.humanID) return "human";
    return id;
  }

  allianceRequest(target: unknown): Snapshot {
    const game = this.requireGame();
    const executor = this.requireExecutor();
    const intent = {
      type: "allianceRequest",
      clientID: CLIENT_ID,
      recipient: this.resolveDiploTarget(target),
    } as StampedIntent;
    this.submit(intent);
    return this.snapshot("ok");
  }

  allianceReject(requestor: unknown): Snapshot {
    const game = this.requireGame();
    const executor = this.requireExecutor();
    // Reject answers an INCOMING pending request; with none from this
    // requestor there is nothing to answer, so reject early.
    const wanted = this.resolveDiploTarget(requestor);
    const pending = game
      .player(this.humanID)
      .incomingAllianceRequests()
      .some((r) => r.requestor().id() === wanted);
    if (!pending) {
      throw new Error(
        `invalid alliance reject: no incoming request from ${JSON.stringify(requestor)}`,
      );
    }
    const intent = {
      type: "allianceReject",
      clientID: CLIENT_ID,
      requestor: wanted,
    } as StampedIntent;
    this.submit(intent);
    return this.snapshot("ok");
  }

  allianceExtend(target: unknown): Snapshot {
    const game = this.requireGame();
    const executor = this.requireExecutor();
    const intent = {
      type: "allianceExtension",
      clientID: CLIENT_ID,
      recipient: this.resolveDiploTarget(target),
    } as StampedIntent;
    this.submit(intent);
    return this.snapshot("ok");
  }

  breakAlliance(target: unknown): Snapshot {
    const game = this.requireGame();
    const executor = this.requireExecutor();
    const intent = {
      type: "breakAlliance",
      clientID: CLIENT_ID,
      recipient: this.resolveDiploTarget(target),
    } as StampedIntent;
    this.submit(intent);
    return this.snapshot("ok");
  }

  embargo(target: unknown, action: unknown): Snapshot {
    const game = this.requireGame();
    const executor = this.requireExecutor();
    if (action !== "start" && action !== "stop") {
      throw new Error(
        `invalid embargo action: expected "start" or "stop", got ${JSON.stringify(action)}`,
      );
    }
    const intent = {
      type: "embargo",
      clientID: CLIENT_ID,
      targetID: this.resolveDiploTarget(target),
      action,
    } as StampedIntent;
    this.submit(intent);
    return this.snapshot("ok");
  }

  private checkDonationAmount(kind: string, amount: unknown): number {
    if (
      typeof amount !== "number" ||
      !Number.isInteger(amount) ||
      amount <= 0
    ) {
      throw new Error(
        `invalid ${kind} amount: expected a positive integer, got ${JSON.stringify(amount)}`,
      );
    }
    return amount;
  }

  donateGold(target: unknown, amount: unknown): Snapshot {
    const game = this.requireGame();
    const executor = this.requireExecutor();
    const intent = {
      type: "donate_gold",
      clientID: CLIENT_ID,
      recipient: this.resolveDiploTarget(target),
      gold: this.checkDonationAmount("gold", amount),
    } as StampedIntent;
    this.submit(intent);
    return this.snapshot("ok");
  }

  donateTroops(target: unknown, amount: unknown): Snapshot {
    const game = this.requireGame();
    const executor = this.requireExecutor();
    const intent = {
      type: "donate_troops",
      clientID: CLIENT_ID,
      recipient: this.resolveDiploTarget(target),
      troops: this.checkDonationAmount("troops", amount),
    } as StampedIntent;
    this.submit(intent);
    return this.snapshot("ok");
  }

  grid(step: unknown): {
    tick: number;
    step: number;
    cols: number;
    rows: number;
    cells: string;
    legend: Record<string, string>;
    nations: { id: string; name: string }[];
  } {
    const game = this.requireGame();
    const gameMap = game.map();
    // Read-only ownership sample: no intents, no game mutation — the same
    // board any observer sees, downsampled for cheap capture.
    if (typeof step !== "number" || !Number.isInteger(step) || step < 4) {
      throw new Error(`invalid grid step: ${JSON.stringify(step)}`);
    }
    const w = game.width();
    const h = game.height();
    const cols = Math.ceil(w / step);
    const rows = Math.ceil(h / step);
    const pool = (
      "abcdfgijklmnpqrsuvwxyzABCDFGIJKMNPQRSUVWXYZ*#+/=%@?"
    ).split("");
    const nationChar = new Map<string, string>();
    this.nationIDs.forEach((id, index) => {
      nationChar.set(id, pool[index % pool.length]);
    });
    const legend: Record<string, string> = {
      ".": "water",
      " ": "land",
      H: "human",
      T: "tribe",
    };
    for (const [id, char] of nationChar) {
      legend[char] = id;
    }
    let cells = "";
    let runChar = "";
    let runLen = 0;
    const flush = () => {
      if (runLen === 0) return;
      cells += runLen === 1 ? runChar : `${runChar}${runLen}`;
      runChar = "";
      runLen = 0;
    };
    for (let gy = 0; gy < rows; gy++) {
      for (let gx = 0; gx < cols; gx++) {
        const ref = gameMap.ref(gx * step, gy * step);
        const owner = game.owner(ref) as unknown as {
          isPlayer?: () => boolean;
          id?: string | (() => string);
        };
        let char: string;
        if (typeof owner.isPlayer === "function" && owner.isPlayer()) {
          const raw = owner.id;
          const id = String(typeof raw === "function" ? raw.call(owner) : raw);
          if (id === this.humanID) char = "H";
          else if (nationChar.has(id)) char = nationChar.get(id) as string;
          else char = "T";
        } else {
          char = gameMap.isLand(ref) ? " " : ".";
        }
        if (char === runChar) {
          runLen++;
        } else {
          flush();
          runChar = char;
          runLen = 1;
        }
      }
    }
    flush();
    return {
      tick: game.ticks(),
      step,
      cols,
      rows,
      cells,
      legend,
      nations: this.nationIDs.map((id) => ({
        id,
        name: game.hasPlayer(id) ? game.player(id).name() : id,
      })),
    };
  }

  moveWarship(unitID: unknown, x: unknown, y: unknown): Snapshot {
    const game = this.requireGame();
    const executor = this.requireExecutor();
    // Production path: a move_warship intent becomes a
    // MoveWarshipExecution, the same one a human patrol order takes. The
    // engine validates the water component; here we check the id resolves
    // to a live human warship and the tile bounds.
    const wanted = String(unitID);
    const ship = game
      .player(this.humanID)
      .units([UnitType.Warship])
      .find((u) => String(u.id()) === wanted);
    if (
      (typeof unitID !== "string" && typeof unitID !== "number") ||
      ship === undefined
    ) {
      throw new Error(
        `invalid warship id: no such human warship ${JSON.stringify(unitID)}`,
      );
    }
    for (const [label, value, max] of [
      ["x", x, game.width()],
      ["y", y, game.height()],
    ] as const) {
      if (
        typeof value !== "number" ||
        !Number.isInteger(value) ||
        value < 0 ||
        value >= max
      ) {
        throw new Error(
          `invalid patrol ${label}: expected an integer in [0, ${max}), got ${JSON.stringify(value)}`,
        );
      }
    }
    const intent = {
      type: "move_warship",
      clientID: CLIENT_ID,
      unitIds: [ship.id()],
      tile: game.ref(x as number, y as number),
    } as StampedIntent;
    this.submit(intent);
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

  // Coastal landing spots reachable by transport ship. Derived from a sample
  // of the human's own shore tiles: trace each cardinal direction across
  // water and report the first foreign or neutral land hit. The agent has no
  // map/terrain coordinates at all, so without this list boat orders would
  // be unaimable guesses. Only the first landfall per ray is reported, so
  // every entry sits on a straight, water-only line from human territory.
  private boatTargets(game: Game, player: Player): BoatTargetState[] {
    const shores = Array.from(player.borderTiles()).filter((t) =>
      game.isShore(t),
    );
    if (shores.length === 0) return [];
    const directions: [number, number][] = [
      [0, -1],
      [0, 1],
      [-1, 0],
      [1, 0],
    ];
    const targets: BoatTargetState[] = [];
    const seen = new Set<number>();
    const step = Math.max(1, Math.ceil(shores.length / 40));
    const maxRange = 30;
    for (let i = 0; i < shores.length && targets.length < 8; i += step) {
      const shore = shores[i];
      const sx = game.x(shore);
      const sy = game.y(shore);
      for (const [dx, dy] of directions) {
        let crossedWater = false;
        for (let d = 1; d <= maxRange; d++) {
          const x = sx + dx * d;
          const y = sy + dy * d;
          if (!game.isValidCoord(x, y)) break;
          const tile = game.ref(x, y);
          if (game.isWater(tile)) {
            crossedWater = true;
            continue;
          }
          if (!crossedWater) break; // same shoreline, no crossing here
          if (game.isImpassable(tile) || game.hasFallout(tile)) break;
          if (seen.has(tile)) break;
          const owner = game.owner(tile);
          if (owner === player) break;
          if (owner.isPlayer() && player.isFriendly(owner)) break;
          const playerOwner = owner.isPlayer() ? (owner as Player) : null;
          seen.add(tile);
          targets.push({
            x,
            y,
            owner: playerOwner
              ? this.labelForPlayerID(playerOwner.id())
              : "neutral",
            troops: playerOwner ? playerOwner.troops() : null,
            tiles: playerOwner ? playerOwner.numTilesOwned() : null,
          });
          break;
        }
      }
    }
    return targets;
  }

  private snapshot(status: string): Snapshot {
    const game = this.requireGame();
    const player = game.player(this.humanID);
    this.refreshTribeIDs(game);
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
      tribes: game
        .players()
        .filter(
          (p) => p.id() !== this.humanID && !this.nationIDs.includes(p.id()),
        ).length,
      tribe_list: this.tribeIDs.map((id, index) => {
        if (!game.hasPlayer(id)) {
          return {
            id: `tribe-${index + 1}`,
            name: "fallen tribe",
            type: "tribe" as const,
            troops: 0,
            tiles: 0,
            alive: false,
            borders_human: false,
          };
        }
        const tribe = game.player(id);
        return {
          id: `tribe-${index + 1}`,
          name: tribe.name(),
          type: "tribe" as const,
          troops: tribe.troops(),
          tiles: tribe.numTilesOwned(),
          alive: tribe.isAlive(),
          borders_human: player.sharesBorderWith(tribe),
        };
      }),
      boats: player.units([UnitType.TransportShip]).map((boat) => ({
        id: String(boat.id()),
        troops: boat.troops(),
      })),
      boat_targets: this.boatTargets(game, player),
      // All human units except transport ships (those live under boats, and
      // humans manage them through the boat UI, not the build menu).
      units: player
        .units()
        .filter((u) => u.type() !== UnitType.TransportShip)
        .map((u) => {
          const tile = u.tile();
          return {
            id: String(u.id()),
            type: u.type(),
            level: u.level(),
            x: game.x(tile),
            y: game.y(tile),
            troops: u.troops(),
            under_construction: u.isUnderConstruction(),
          };
        }),
      alliances: player.alliances().map((a) => {
        const other = a.other(player);
        return { id: this.labelForPlayerID(other.id()), name: other.name() };
      }),
      alliance_requests: {
        incoming: player
          .incomingAllianceRequests()
          .filter((r) => r.status() === "pending")
          .map((r) => this.labelForPlayerID(r.requestor().id())),
        outgoing: player
          .outgoingAllianceRequests()
          .filter((r) => r.status() === "pending")
          .map((r) => this.labelForPlayerID(r.recipient().id())),
      },
      embargoes: player.getEmbargoes().map((e) => {
        const target = e.target;
        return { id: this.labelForPlayerID(target.id()), name: target.name() };
      }),
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
          immune: nation.isImmune(),
          borders_human: player.sharesBorderWith(nation),
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
  spawnX?: number | null;
  spawnY?: number | null;
  nations?: number;
  difficulty?: string;
  mapSize?: string;
  tribes?: number;
  ticks?: number;
  target?: unknown;
  troops?: unknown;
  attackID?: unknown;
  unitID?: unknown;
  unit?: unknown;
  step?: unknown;
  action?: unknown;
  amount?: unknown;
  x?: unknown;
  y?: unknown;
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
          request.spawnX ?? null,
          request.spawnY ?? null,
          request.nations ?? 0,
          request.difficulty ?? "easy",
          request.mapSize ?? "full",
          request.tribes ?? 0,
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
      case "cancel_attack":
        writeResponse({
          id,
          ok: true,
          result: session.cancelAttack(request.attackID),
        });
        return true;
      case "boat":
        writeResponse({
          id,
          ok: true,
          result: session.boatAttack(request.x, request.y, request.troops),
        });
        return true;
      case "cancel_boat":
        writeResponse({
          id,
          ok: true,
          result: session.cancelBoat(request.unitID),
        });
        return true;
      case "build":
        writeResponse({
          id,
          ok: true,
          result: session.buildUnit(request.unit, request.x, request.y),
        });
        return true;
      case "upgrade":
        writeResponse({
          id,
          ok: true,
          result: session.upgradeUnit(request.unitID),
        });
        return true;
      case "delete_unit":
        writeResponse({
          id,
          ok: true,
          result: session.deleteUnit(request.unitID),
        });
        return true;
      case "alliance_request":
        writeResponse({
          id,
          ok: true,
          result: session.allianceRequest(request.target),
        });
        return true;
      case "alliance_reject":
        writeResponse({
          id,
          ok: true,
          result: session.allianceReject(request.target),
        });
        return true;
      case "alliance_extend":
        writeResponse({
          id,
          ok: true,
          result: session.allianceExtend(request.target),
        });
        return true;
      case "break_alliance":
        writeResponse({
          id,
          ok: true,
          result: session.breakAlliance(request.target),
        });
        return true;
      case "embargo":
        writeResponse({
          id,
          ok: true,
          result: session.embargo(request.target, request.action),
        });
        return true;
      case "donate_gold":
        writeResponse({
          id,
          ok: true,
          result: session.donateGold(request.target, request.amount),
        });
        return true;
      case "donate_troops":
        writeResponse({
          id,
          ok: true,
          result: session.donateTroops(request.target, request.amount),
        });
        return true;
      case "move_warship":
        writeResponse({
          id,
          ok: true,
          result: session.moveWarship(request.unitID, request.x, request.y),
        });
        return true;
      case "grid":
        writeResponse({ id, ok: true, result: session.grid(request.step) });
        return true;
      case "save_record":
        writeResponse({ id, ok: true, result: session.saveRecord() });
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
