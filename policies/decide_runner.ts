// Harness helper (not agent-editable): replay recorded overviews through
// a TS policy for differential testing and divergence probes.
//
// Reads JSON overviews (one per line) on stdin, writes JSON order lists
// (one per line) on stdout. Run from the repo root:
//   node policies/decide_runner.ts [policy-path] < overviews.jsonl
// With no path it loads ./evolve_me.ts; otherwise the given .ts source
// or bundled .mjs (resolved against the cwd).
import * as path from "node:path";
import * as readline from "node:readline";
import { pathToFileURL } from "node:url";

const target =
  process.argv[2] ?? path.join(import.meta.dirname, "evolve_me.ts");
const module = await import(
  pathToFileURL(path.resolve(target)).href
) as {
  EvolvingPolicy: new () => { decide: (overview: unknown) => unknown };
};
const policy = new module.EvolvingPolicy();
const rl = readline.createInterface({ input: process.stdin });

rl.on("line", (line: string) => {
  if (line.trim() === "") {
    return;
  }
  const orders = policy.decide(JSON.parse(line));
  process.stdout.write(JSON.stringify(orders) + "\n");
});
