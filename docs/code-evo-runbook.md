# Code-evo runbook (research loop v2)

Autoresearch-style loop, headless only (no MCP/LLM live play anywhere):
the agent edits ONLY `evolve_me.py` (policy script) and appends to
`research_log.md` (lab notebook) — enforced post-hoc, violations reject
the round. The headless evaluator scores each shipped candidate over
the 8 fixed Europe spawns (`config/spawns/europe-8.json`: 52 nations +
400 tribes, medium) to 100,000 ticks or elimination, 8 games in
parallel (`--jobs 8`). Score = `tiles_peak + 5 * survival_ticks`
(+500,000 human win); candidate score = mean over spawns.
Each spawn plays a distinct but reproducible world (`gameId` derived
from the run name + spawn id); same spawn replays the same world.

World schemes (`--world-scheme`, default `compact` for new runs):

- `compact`: 8-alnum FNV-1a ids. The archived-GameRecord schema
  (converter AND client) only accepts `^[A-Za-z0-9]{8}$` gameIDs, and
  the client re-derives tribe/nation ids by seeding from the recorded
  gameID — so the tape label must equal the live seed or replays
  silently drop every tribe/nation-targeted attack (`target not
  found`; only expands render). Compact ids satisfy both: tapes
  stage in the hub AND replay faithfully.
- `legacy`: frozen 32-char ids. Reproduces pre-compact worlds exactly
  (scores compare within a scheme, never across), but tapes replay
  expands only. Kept so in-flight runs keep their worlds; do not use
  for new runs.

Tapes carry a state hash every 50 ticks (native singleplayer cadence
is every 100). The client verifies replay hashes against these and
raises desync instead of silently simulating a skewed world — the
tripwire that catches any future seed/label split.

Baseline v2 (Impossible port, acts every decision = every 50 ticks):
mean 57916 / min 28204 on europe-8
(`raw/openfront-code-evo-v2-baseline-20260920-1137/`). Beat this.

## Score the baseline (no model, no key)

```bash
uv run python -m openfrontbench.code_evo.evolve \
  --spawns config/spawns/europe-8.json \
  --output <fresh-dir> --jobs 8 --evaluate-only
```

Tiny smoke (fast, plains):

```bash
uv run python -m openfrontbench.code_evo.evolve \
  --spawns config/spawns/europe.json \
  --output <fresh-dir> --nations 0 --tribes 0 --max-ticks 150 \
  --evaluate-only
```

Note: `--nations/--tribes/--max-ticks` override the registry defaults;
omit them for the production gauntlet (52/400/100k).

## Research run (needs OPENFRONT_MODEL + provider key in .env.local)

```bash
uv run python -m openfrontbench.code_evo.evolve \
  --spawns config/spawns/europe-8.json \
  --output <fresh-dir> --iterations 20 --jobs 8
```

Each iteration: harness appends a header to the master
`research_log.md`, the isolated opencode research agent (read: whole
repo + full log history; write: the two files only) edits its copies,
and ends its log section with `VERDICT: SHIP|HOLD` + `REASON`. A
divergence probe (candidate vs parent order streams, 500 ticks × 2
spawns) auto-HOLDs edits that never fire — no full eval spent. SHIP
(or every 4th iteration, forced) triggers the parallel 8-spawn eval;
results go to `program_db.jsonl`, the per-iter eval dir (tapes +
summaries), and the log. 6 stagnant iterations switch parenting to
the diverse entry. The coding agent model/timeout come from
`OPENFRONT_MODEL` / `--agent-timeout` (allow generous timeouts;
scripted analysis is by reasoning over code + log — the agent runs
no commands).

What earns a SHIP: name the exact trigger state, cite log evidence it
occurred in a parent game (per-spawn `out`/`gpeak`/`tpeak`/`city`),
predict which spawns' streams will differ. "Pure upside / cannot
hurt" framings are HOLDs.

## What the scores mean

`aggregate.json`: `mean_score` (selection), `min_score` (robustness),
`wins`, per-spawn `tiles_peak/final_tiles/ticks/policy_errors` plus
conquered `spawn_tile` and `game_id` (world). Past reference: v1
passive baseline died by ~2k ticks (mean 9989 on 4 spawns); v2
acts-every-50-ticks baseline reaches 2.6k-8.8k ticks (mean 57916 on
8 spawns).

## Hub: experiments, unified outputs, retention

Every finished game writes the same bundle: `record.json` (replay tape,
always captured), `summary.json` (unified schema — pipeline, model /
policy, map, spawn, score, tiles, ticks, winner), plus pipeline-native
files (`live_result.json`, `aggregate.json`). Game dirs nest under an
experiment dir with `experiment.json` (new `run_cycle` runs go to
`raw/openfront-cycles-<stamp>/attempt-N-*`; evolve iters group under
the run root). Pre-unification flat runs show as `legacy-runs`.

View: start the vendor client, then the index (it lists experiments;
click through to a suite, then watch):

```bash
npm run start:client          # vendor/OpenFrontIO (serves :9001 here)
uv run python scripts/serve_replays.py --raw raw/ --port 8787 --client-port 9001
```

Retention is manual: to reclaim disk, delete `record.json` inside game
dirs you no longer need to watch (keep `summary.json` +
`experiment.json` — the index still lists the scores). Never delete an
experiment's `experiment.json` while its games remain. `raw/` is
gitignored; nothing there is committed.
