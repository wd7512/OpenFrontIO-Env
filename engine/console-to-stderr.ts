// Route every non-error console channel to stderr so the JSONL protocol on
// stdout stays clean. Imported first from worker.ts, so ESM evaluation order
// installs the overrides before the vendor core modules are evaluated.
const toStderr =
  (stream: NodeJS.WriteStream) =>
  (...args: unknown[]): void => {
    stream.write(
      args
        .map((a) => (typeof a === "string" ? a : JSON.stringify(a)))
        .join(" ") + "\n",
    );
  };

console.log = toStderr(process.stderr);
console.info = toStderr(process.stderr);
console.debug = toStderr(process.stderr);

export {};
