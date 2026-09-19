# Memory - Europe Solo Hard FFA - ENGINE01

## Match recap (concrete numbers - use these, not vibes)
- Format: Europe Normal, Singleplayer FFA, difficulty Hard, nations 52, bots/tribes 400, randomSpawn false.
- Result: LOSS. final_human tiles 0, troops 3970. winner null. timed_out false.
- Length: 39 decisions, ticks 53 -> 1953 (50 ticks/decision), 120 tool calls, 302s wall, 311s duration.
- End board: all 52 nations alive. Human at 0 vs leaders:
  Finland 83903 tiles / 841923 troops, Belarus 87710 / 1282664, Russia 78325 / 855747,
  Iraq 76714 / 991605, Tunisia 76178 / 1401040, Sweden 73670 / 1128603,
  Kazakhstan 70854 / 1198907, Georgia 66696 / 943160, Ukraine 66313 / 854080,
  Algeria 63975 / 1484613, Morocco 61656 / 1115823.
- Troop leaders to avoid late: Turkiye 1633554, Norway 1605604, Algeria 1484613,
  Tunisia 1401040, Iceland 1385545, Sapmi 1304457, Belarus 1282664, Greece 1284024.
- Weakest at end: Serbia 160 tiles / 61423 troops, Germany 26778 tiles / 215500 troops (lowest troop holder among large), Egypt 6146 tiles / 361384 troops.
- Tape: record.json gameId ENGINE01, 1953 ticks. Single-line tape truncated on read, order-by-order counts not recoverable - notes below use final tally + engine/adapter rules.

## What won tiles (same format)
- Early expand (attack target expand = null -> TerraNullius) is the only safe tile source. Nations start from seeded spawns, tribes 400 blanket the map - neutral land goes first 5-10 decisions.
- Bordering tribes are the second tile bank: session only lists bordering tribes in tribes_list, worker keeps tribe-N stable. If borders_human false, attack retreats silent - check projection before committing troops.
- Never count distant nations as targets: no shared border = retreat, wasted decision.

## What bled troops
- Ended 0 tiles / 3970 troops vs nation average ~700k-1M. Means late-game attrition vs 1M+ stacks (Turkiye, Norway, Algeria class) wipes any small foothold.
- Hard difficulty nations scale fast: by tick 1953 even mid nations hold 500k-900k (France 606k, Italy 550k, England 567k). Any 1v1 trade with <100k human stack loses.
- 120 tool calls / 39 decisions = ~3 orders per decision. Over-ordering attacks without 50-tick settle bleeds troops - advance, then re-query before re-attacking.

## When to strike
- Decisions 1-10 (ticks 53-503): expand only, grow base. Do not touch nation-N while immune flag can be true.
- Decisions 10-25: eat only bordering tribes + Serbia/Egypt-class weak neighbors if borders_human true. Germany-class 215k is the ceiling - do not hit 800k+ stacks.
- After tick ~1250: only strike if you hold >30k tiles and >500k troops. This match had 0 at 1953 - game was lost before tick 1500. If under 10k tiles by decision 25, turtle and pick weakened edge, do not feed leaders.

## What to never repeat
- Never play 52-nation + 400-tribe Europe Hard as extended war: 52 survivors means no one cleans for you. Dying with 3970 troops left = fed someone else.
- Never attack non-bordering nation-N / tribe-N: worker.ts retreats silent, session hides distant tribes. Verify borders_human true in overview first.
- Never boat / build blind: boat needs water-component tile, builds (city, defense-post, sam-launcher, missile-silo, port, factory, atom-bomb, hydrogen-bomb, mirv, warship) need owned land + gold. Failed orders still cost a decision window.
- Never go to 39 decisions with no city/port economy: final 0 tiles proves expansion without consolidation collapses. Build city early, then port/factory if alive past tick 500.
- Never ignore Serbia/Germany/Egypt signals: Serbia survived on 160 tiles, Germany on 215k troops - those are the only punishable targets in a 52-alive board. Hitting Finland/Belarus/Turkiye stacks is suicide.

## Next-player checklist (Europe solo Hard)
1. Start: expand 3-5x, check tiles/troops each decision, stop at 50-tick cadence.
2. Build city on owned land by decision 5-8, else economy never compounds.
3. Only order nation-N if borders_human true, immune false, target troops <1.5x yours.
4. Prefer tribe-N over nation-N while tribes border you - cheaper tiles.
5. If tiles <10k by tick 1253, stop attacking leaders, consolidate edge and wait for weak (Serbia/Germany-type) opening.
