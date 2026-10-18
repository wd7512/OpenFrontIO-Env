/** Client-path replay verification: replays a served tape through the real
 * createGameRunner pipeline (the same code the browser runs) and checks the
 * re-simulated winner + tick against the tape's declared outcome.
 *
 * One process per game: the terrain cache is shared per module registry, so
 * each game replays in a fresh process — exactly like the browser, which
 * constructs a new Worker per game.
 *
 * Usage: tsx scripts/verify_replay.ts OF000018 [--archive http://127.0.0.1:8787]
 */
import path from "path";
import { fileURLToPath } from "url";
import { createGameRunner } from "../vendor/OpenFrontIO/src/core/GameRunner";
import {
  GameRecordSchema,
  type GameStartInfo,
} from "../vendor/OpenFrontIO/src/core/Schemas";
import {
  decompressGameRecord,
  toWireGameStartInfo,
} from "../vendor/OpenFrontIO/src/core/Util";
import { NodeGameMapLoader } from "../vendor/OpenFrontIO/tests/perf/fullgame/NodeGameMapLoader";

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

async function main(): Promise<void> {
  const route = process.argv[2];
  const archiveFlag = process.argv.indexOf("--archive");
  const archive =
    archiveFlag >= 0 && process.argv[archiveFlag + 1]
      ? process.argv[archiveFlag + 1]
      : "http://127.0.0.1:8787";
  if (!route) throw new Error("usage: verify_replay.ts OFxxxxxx [--archive URL]");
  const recordJson = await (await fetch(`${archive}/game/${route}`)).json();
  const meta = await (await fetch(`${archive}/game/${route}/meta`)).json();
  const record = decompressGameRecord(GameRecordSchema.parse(recordJson));
  const gameStart: GameStartInfo = toWireGameStartInfo(record.info);
  if (typeof meta?.behavior === "string" && meta.behavior !== "production") {
    gameStart.nationBehavior = meta.behavior;
  }
  const mapLoader = new NodeGameMapLoader(path.join(REPO_ROOT, "vendor/OpenFrontIO/resources/maps"));
  const runner = await createGameRunner(gameStart, undefined, mapLoader, () => {});
  for (const turn of record.turns) runner.addTurn(turn);
  let ticks = 0;
  while (runner.executeNextTick()) {
    if (++ticks > record.turns.length + 100) {
      console.log(`${route}: OVERRUN`);
      process.exit(1);
    }
  }
  const gr = runner as unknown as {
    game: { ticks(): number; getWinner(): { name?: () => string } | null };
  };
  const w = gr.game.getWinner();
  const name = typeof w?.name === "function" ? w.name() : w;
  const ok = gr.game.ticks() === meta.declared_tick && name === meta.winner;
  console.log(
    `${route}: ${meta.game} -> winner=${name} ticks=${gr.game.ticks()} ` +
      `(expect ${meta.winner} @ ${meta.declared_tick}) ` +
      (ok ? "FAITHFUL" : "DIVERGED"),
  );
  process.exit(ok ? 0 : 1);
}
main();
