# Memory — Europe FFA Solo vs 52 Nations + 400 Tribes (ENGINE01)

## Match recap (concrete numbers — use these, not vibes)
- Format: Europe Normal, FFA Singleplayer, Hard, `nations=52`, `bots/tribes=400`, `randomSpawn=false`, `infiniteGold/Troops=false`, `instantBuild=false`.
- Length: 1953 ticks / 39 decisions (ticks 53→1953, 50 ticks/decision), 121 tool calls (~3.1/decision), 379s wall, cost 0.00135, `timed_out=false`, `winner=null`.
- Final human (Agent): 0 tiles, 3761 troops — eliminated. All 52 nations alive.
- Gap: human 0 tiles vs smallest nation Serbia 283 tiles / 143,468 troops; vs leaders Belarus 87,404 tiles / 1,223,932 troops, Finland 83,903 / 841,923, Russia 78,325 / 855,747, Tunisia 76,178 / 1,332,358.
- Troop gap: human 3,761 vs weakest Germany 217,502 (57x) vs top Greece 1,736,643 (461x), Norway 1,605,604, Algeria 1,484,613. Mid-pack ~700-900k (Poland 929k, Latvia 926k, Estonia 943k).
- Record tape: `record.json` header confirms ENGINE01 / europe mapDir / same config; full turn tape was single-line truncated in review, so no turn-by-turn order counts recovered — lessons below from final score + engine/adapter rules.

## What won tiles (for NEXT player)
- Early `expand` (attack null-target = TerraNullius) is the only safe tile source. Nations started ~4k–87k tiles by tick 1953; you need thousands of tiles by decision 5–10 (tick ~250–550) to stay relevant.
- Border-gated attacks only: engine auto-retreats nation/tribe attacks with no shared border (silent fail). Check `borders_human` + `immune` before any `nation-N` order.
- Tribes: adapter only *lists* bordering tribes (`tribes_list`), but *any* `tribe-N` is orderable via worker IDs. 400 tribes = free early farm if bordering; distant ones waste troops.

## What bled troops
- Fighting Hard nations head-on at 3k vs 500k–1.7M stacks = instant bleed. Never trade with Greece/Norway/Algeria/Belarus/Tunisia stacks (>1.2M).
- Unchecked expansion without defense-post/city economy: gold-starved builds fail (engine validates gold/cost/tile, acceptance ≠ landing). No tiles = no income = death spiral to 0.
- Boat/warship misuse: boat intents validate destination tile + water component; warship patrol only lands on water in same component. Bad water orders = lost troops + lost decision.
- Diplomacy gifts to non-allies: `donate_gold/troops` silently refused unless allied. Alliance requests answered on AI schedule or never — don't budget around them.

## When to strike
- Decisions 1–6 (ticks 53–353): pure expand + border tribes only. No nation attacks while `immune` or non-bordering.
- Decisions ~6–15 (ticks 353–803): only hit Serbia-class weaklings (sub-500 tiles / sub-200k troops pattern — here Serbia 283 / Germany 217k were weakest) *if* bordering + not immune + you have >10x their troops locally.
- After tick ~1000 with <20k tiles: do NOT start new nation wars. Consolidate, build city/factory/defense-post, embargo/break/alliance-extend defensively. This match had no winner by 1953 — survival > elimination attempts.
- One decision = 50 ticks. Cancel/retreat (`cancel_attack` / `cancel_boat`) same decision if projection shows `retreating=true` or no shared border.

## Never repeat
- Never end 0 tiles / 3.7k troops vs 52 alive nations: that means over-attacked nations early and under-expanded neutral land. 39 decisions, 121 calls did not prevent elimination — volume ≠ strategy.
- Never order `nation-N` without checking `borders_human=true`, `immune=false`, `alive=true`, and troop math (need local superiority vs 700k+ mid-pack).
- Never donate/embargo/alliance-request blind: verify label (`nation-1..52` + bordering `tribe-N`), verify incoming-request list before reject, verify live `attacks[].id` / `boats[].id` before cancel.
- Never waste builds: allowlist only `city, defense-post, sam-launcher, missile-silo, port, factory, atom-bomb, hydrogen-bomb, mirv, warship` (kebab-case); needs owned land (structures) / water access (warship); max 1,000,000 troops per attack order.
- Next run checklist: spawn → expand every decision until >10k tiles → farm border tribe-N → city+defense → only then consider weakest bordering nation. If tiles stall by tick 500, abort nation war immediately.
