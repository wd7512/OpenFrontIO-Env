import { AttackExecution } from "../vendor/OpenFrontIO/src/core/execution/AttackExecution";
import { SpawnExecution } from "../vendor/OpenFrontIO/src/core/execution/SpawnExecution";
import {
  Execution,
  Game,
  Nation,
  Player,
} from "../vendor/OpenFrontIO/src/core/game/Game";
import { GameID } from "../vendor/OpenFrontIO/src/core/Schemas";

// Improved-Hard nation: Hard economy (difficulty stays "hard", so
// Config startManpower/maxTroops/troopIncreaseRate are untouched) with
// threshold-ratio expansion logic instead of AiAttackBehavior:
//
//   every 52 ticks (≈ Hard attackRate mean): if troops >= 38% of max,
//   send 15% of current troops at TerraNullius.
//
// This is the game-verified 52-tick optimum from analysis/ (model 7824,
// game 7825/7831 center-spawn). No structures, no diplomacy, no boats —
// pure expansion, like the sweep agent, but wired as a real Nation
// (bot name, nation spawn, nation economy).
const DECISION_INTERVAL = 52;
const THRESHOLD = 0.38;
const RATIO = 0.15;

export class ImprovedHardExecution implements Execution {
  private active = true;
  private mg!: Game;
  private player: Player | null = null;
  private spawnExecAdded = false;
  private firstDecisionTick = -1;

  constructor(
    private gameID: GameID,
    private nation: Nation,
  ) {}

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

  tick(ticks: number) {
    const player = this.player;
    if (player === null) {
      return;
    }
    // Spawn path: land via SpawnExecution with random placement (the
    // production HumansVsNations path), regardless of manifest spawn cells,
    // so each game_id seeds a distinct start. Mirrors the
    // spawnCell-undefined branch of NationExecution.
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
