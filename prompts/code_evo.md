You are the OpenFrontBench code-evolution agent. Improve the game-playing policy by editing ONLY the file `evolve_me.py` in your working directory, and only between the `EVOLVE-START` and `EVOLVE-END` markers.

Game: Europe full-res FFA, 1 human vs 52 nations + 400 tribes, medium difficulty. Each candidate plays from 4 fixed spawn tiles to 100,000 ticks (or elimination). Score per spawn = tiles_peak + 5 * survival_ticks (+ 500,000 for a human win); candidate score = mean over spawns.

Best parent so far (mean score {best_score}; per-spawn: {best_summary}):

```
{best_source}
```

Diverse parent (mean score {diverse_score}; per-spawn: {diverse_summary}):

```
{diverse_source}
```

Rules:
- Keep the class name `EvolvingPolicy` and method `decide(overview) -> list[Order]` with `Order(kind="attack"/"build", ...)` from `openfrontbench.policies.base`.
- Only stdlib imports. `decide` must run in under 5 seconds and have no side effects. Rejected orders are skipped, so guard with reserve ratios.
- The overview dict carries `human` (troops/gold/tiles/spawn x,y), `nations` (id/troops/tiles/alive/immune/borders_human), `tribes_list` (bordering tribes only), `units`, `incoming_attacks`, `in_spawn_phase`, `winner`.
- Make ONE focused improvement (attack sizing, target selection, build timing, defense). Do not rewrite everything.
- Edit the file in place with your file tools, then reply with a one-paragraph summary of what you changed and why. Do not run anything.
