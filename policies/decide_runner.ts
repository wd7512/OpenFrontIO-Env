// Harness helper (not agent-editable): replay recorded overviews through
// the TS policy for differential testing against the Python champion.
//
// Reads JSON overviews (one per line) on stdin, writes JSON order lists
// (one per line) on stdout. Run from the repo root:
//   node policies/decide_runner.ts < overviews.jsonl
import { EvolvingPolicy } from "./evolve_me.ts";
import * as readline from "node:readline";

const policy = new EvolvingPolicy();
const rl = readline.createInterface({ input: process.stdin });

rl.on("line", (line: string) => {
  if (line.trim() === "") {
    return;
  }
  const orders = policy.decide(JSON.parse(line));
  process.stdout.write(JSON.stringify(orders) + "\n");
});
