# Strategy Notes - NEXT Solo Europe Hard Player

Source match: ENGINE01 - Europe Normal full-res, FFA Singleplayer, Hard, 52 nations, 400 tribes/bots, donateGold/Troops false.
Result file: live_result.json, scenario=solo, winner=null, timed_out=false, 61 decisions, 170 tool calls, 3053 ticks, 539.7s wall.
Tape: record.json (gameId ENGINE01) - turns present but single-line truncated on read, only header recoverable. Orders below inferred from result + worker.ts/session.py mechanics, not invented tape details.

## Final score - concrete
- Human (Agent): 20311 tiles, 109919 troops after tick 3053.
- Decision cadence: ticks 53,103,153...3053 = 50 ticks/decision x61. ~665 tiles net per decision, ~6.6 tiles/tick overall.
- Human rank: bottom third on tiles ( ~15 nations smaller, ~35 larger). Troops lowest among alive except Hungary (78008). Dead: Croatia 0/25955, Serbia 0/12925, England 0/35330.
- Leaders to beat: Russia 159704/1555496, Finland 150783/1180420, Belarus 112067/1071535, Sweden 111130/1496278, Georgia 102851/1490632, Kazakhstan 106578/1663511, Sápmi 75548/1907044 (highest troops), Tunisia 89589/1756712, Libya 51349/1605413.
- Smallest alive to target first if same spawn: Egypt 1033, Hungary 538, Denmark 932, Monaco 5129, Germany 8108, Wales 8676, Ireland 11607.

## What won tiles
- `expand` (attack with null targetID -> TerraNullius) is the only cheap tile source. It is the production expand path in worker.ts `attack()`. Use it every decision early while neutral land exists.
- Bordering tribes only: session.py `_project` lists only `borders_human=true` tribes in `tribes_list`, but any `tribe-N` remains orderable via worker. Distant tribe attacks retreat silent with no shared border. Check `borders_human` before spending troops.
- 400 tribes = free-tile farm if you stay on contiguous neutral/tribal edge. Nations 52 on Europe Normal means boxed in fast - expand outward before nation borders close.

## What bled troops
- Ended 109k vs 1.0-1.9M for top 10 nations. Never trade head-on with 500k+ stack (Sápmi 1.9M, Tunisia 1.75M, Kazakhstan 1.66M, Russia 1.55M, Sweden 1.49M). You lose attrition.
- `attack(target,troops)` requires int 1..1,000,000 (MAX_ATTACK_TROOPS). Overcommitting one large attack leaves home hollow; engine `AttackExecution` + `WinCheckExecution` punishes thin defense vs 52 Hard AIs.
- Donations disabled in config but engine also silently refuses donations to non-allies (session.py `order_donate_*`). Do not gift troops/gold - no return in FFA Hard.
- Boats/warships validated by engine on water component (worker.ts `boatAttack`). Bad water tile = wasted order. Verify `width/height` bounds first.

## When to strike
- Decisions 1-20 (ticks 53-1003): pure expand + border tribes. No nation-X attacks unless target is <10k tiles and `borders_human=true` and not immune (spawn immunity blocks early nation hits - projection `immune` flag).
- Decisions 20-40 (ticks 1003-2003): keep 1 expand running, add second attack only vs dying/smallest (Egypt/Denmark/Hungary/Germany-size) or dead-stack cleanup (Croatia/Serbia/England went to 0 tiles this game - vulture those).
- Decisions 40-61 (ticks 2003-3053): this match stalled at 20k with no winner. Do not sit to 3053 with 109k troops. Consolidate: city/factory/port then upgrade (only port, missile-silo, sam-launcher, city, factory upgradable), defense-post on nation border, then 2:1 local superiority before nation strike.
- Advance is exactly 50 ticks per `end_decision(expected)` - stale/out-of-order rejected. Issue orders then advance one decision at a time.

## Never repeat
1. Do not play to tick 3053 with 20k tiles / 109k troops and null winner. If under 30k tiles by tick 1500, you are behind - stop feeding big nations, farm tribes/neutral only.
2. Do not attack `nation-N` without `borders_human=true` and `immune=false`. It retreats silent, wastes troops and a tool call. 170 calls / 61 decisions (~2.8/decision) this game was too thin to recover bad orders.
3. Do not donate gold/troops in FFA Hard. Config has donate false, engine friendly-only.
4. Do not order `tribe-N` from full list blind - use only projected `tribes_list` (bordering). 400 entries would blow tool window (~45KB) - that is why session filters.
5. Do not build without owned land check: `build_unit` allowlist only: city, defense-post, sam-launcher, missile-silo, port, factory, atom-bomb, hydrogen-bomb, mirv, warship. Engine validates gold/cost/tile - acceptance != landing. Build city/factory early, nukes/warship late.
6. Do not ignore `attacks[].retreating`, `alliances`, `embargoes`, `boats`, `units[].under_construction` in overview - retreat/recall (`cancel_attack`/`cancel_boat` needs live id) promptly if stalled.

## Engine facts to reuse
- Boot Europe: `map_size=full`, `spawn=None` => seeded random land spawn (MAP_BOOT). No fixed (50,50).
- Spawn phase ends only after human + all 52 nations spawned (worker.ts `MAX_SPAWN_TICKS=10` guard).
- Diplomacy rides production intents: allianceRequest/Extend/Break, embargo start/stop, all by `nation-N`/`tribe-N` labels.
