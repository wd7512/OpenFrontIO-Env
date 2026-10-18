import { AttackExecution } from "../vendor/OpenFrontIO/src/core/execution/AttackExecution";
import { SpawnExecution } from "../vendor/OpenFrontIO/src/core/execution/SpawnExecution";
import {
  Execution,
  Game,
  Nation,
  Player,
} from "../vendor/OpenFrontIO/src/core/game/Game";
import { GameID } from "../vendor/OpenFrontIO/src/core/Schemas";

// Externally-driven nation for the 1v1 RL sandbox: the proven Improved-Hard
// expansion autopilot (52-tick cadence, 38% gate, 15% tranches at
// TerraNullius) runs every decision, and harness-injected fight orders are
// drained from the queue ahead of it. Live the worker fills the queue
// between ticks via the nation_order command; replays preload it from the
// taped externalOrders (same code path, same ticks — insertion order is
// identical by construction, so tapes replay bit-for-bit).
// Behavior tag shared with the client replay loader: archived replays whose
// record info carries externalOrders attach ExternalExecution instead of
// the production NationExecution (see Executor.nationExecutions).
export const EXTERNAL_BEHAVIOR = "external";

const DECISION_INTERVAL = 52;
const THRESHOLD = 0.38;
const RATIO = 0.15;

export interface ExternalOrder {
  // Game tick at which the harness injected the order. Drained by the first
  // tick() with a later tick number — live and replay agree because both go
  // through this same drain rule.
  tick: number;
  // Spawn-order nation index (parallel to nationBehaviors); the replay
  // loader preloads each playback execution with its own slice.
  nation: number;
  // Resolved player id (live) / taped player id (replay). Player ids are
  // stable across identical boots (humans first, then nations, one RNG).
  targetID: string;
  troops: number;
}

export class ExternalExecution implements Execution {
  private active = true;
  private mg!: Game;
  private player: Player | null = null;
  private spawnExecAdded = false;
  private firstDecisionTick = -1;
  private queue: ExternalOrder[];

  constructor(
    private gameID: GameID,
    private nation: Nation,
    orders?: ExternalOrder[],
  ) {
    this.queue = orders ? [...orders] : [];
  }

  isActive(): boolean {
    return this.active;
  }

  activeDuringSpawnPhase(): boolean {
    return true;
  }

  init(mg: Game, _ticks: number) {
    this.mg = mg;
    if (!this.mg.hasPlayer(this.nation.playerInfo.id)) {
      this.player = this.mg.addPlayer(this.nation.playerInfo);
    } else {
      this.player = this.mg.player(this.nation.playerInfo.id);
    }
  }

  /** Live path: the worker pushes harness orders here between ticks. */
  enqueue(order: ExternalOrder): void {
    this.queue.push(order);
  }

  tick(ticks: number) {
    const player = this.player;
    if (player === null) {
      return;
    }
    // Spawn path mirrors ImprovedHardExecution (production HumansVsNations
    // random placement), so external tapes share the same worlds as IH.
    if (this.mg.inSpawnPhase()) {
      if (player.hasSpawned() || this.spawnExecAdded) {
        return;
      }
      this.mg.addExecution(
        new SpawnExecution(this.gameID, this.nation.playerInfo),
      );
      this.spawnExecAdded = true;
      return;
    }
    if (!player.hasSpawned()) {
      return;
    }
    if (!player.isAlive()) {
      this.active = false;
      return;
    }
    // Injected fight orders drain before the autopilot, in queue order.
    // Unknown targets (corrupt tape) are skipped loudly-failing would break
    // the replay mid-tick; the skip is deterministic on both sides.
    while (this.queue.length > 0 && this.queue[0].tick < ticks) {
      const order = this.queue.shift()!;
      if (!this.mg.hasPlayer(order.targetID)) {
        continue;
      }
      this.mg.addExecution(
        new AttackExecution(order.troops, player, order.targetID),
      );
    }
    if (this.firstDecisionTick < 0) {
      this.firstDecisionTick = ticks;
    }
    if ((ticks - this.firstDecisionTick) % DECISION_INTERVAL !== 0) {
      return;
    }
    const cap = this.mg.config().maxTroops(player);
    const troops = player.troops();
    if (troops < THRESHOLD * cap) {
      return;
    }
    this.mg.addExecution(
      new AttackExecution(
        troops * RATIO,
        player,
        this.mg.terraNullius().id(),
      ),
    );
  }
}
