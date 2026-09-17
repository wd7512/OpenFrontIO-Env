import { build } from "esbuild";
import path from "node:path";
import { fileURLToPath } from "node:url";

const engineDir = path.dirname(fileURLToPath(import.meta.url));

await build({
  absWorkingDir: engineDir,
  entryPoints: ["worker.ts"],
  outfile: "dist/worker.mjs",
  bundle: true,
  platform: "node",
  format: "esm",
  target: "node22",
  sourcemap: true,
  logLevel: "info",
  // Vendor sources import npm packages (zod, jose, ...). Node resolution from
  // their location cannot see engine/node_modules, so teach esbuild about it.
  nodePaths: [path.join(engineDir, "node_modules")],
  tsconfig: path.join(engineDir, "tsconfig.json"),
});
