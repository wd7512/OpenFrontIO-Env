# Strategy Notes — Next Run, Same Format (Europe Solo FFA)

Source match: `ENGINE01`, Europe Normal, Singleplayer FFA, Easy, 52 nations, 400 bots, no donate/infinite/instant, randomSpawn false.
Seeded random land spawn (europe = full-res, spawn None). 100 decisions x 50 ticks = 5003 ticks, 741s wall, 256 tool calls, returncode 0, winner null.
Final: human 190,019 tiles / 3,359,577 troops — #1 on both, but NO WIN in 5003 ticks.

## 1. What won tiles (do again)
- `expand` (attack null / TerraNullius) is the tile engine. Human reached 190k tiles = 1.54x nearest rival Finland (123,367). Keep 1 expand attack live almost every decision until ~150k tiles.
- Neutral tribes (400 bots at start) are free tiles. Border-only `tribes_list` in projection hides distant tribes, but any `tribe-N` is orderable via worker — cycle tribe targets, don't wait for them to appear in projection.
- 9 nations died without human winning: Poland, Lebanon, Bosnia and Herzegovina, Syria, Hungary, Austria, Portugal, Czechia, Germany. Dead piles still hold up to 27k remnant troops (Bosnia 25,717, Poland 27,559). Mop tiles after collapse; troops evaporate (Syria 0/0, Germany 0/0).
- Small alive nations are cheap tiles: Romania 278 tiles, Northern Ireland 362, Albania 856, Scotland 895, Jordan 1,562, France 3,853, Libya 4,922, Wales 4,332. One focused `nation-N` hit each; do not leave 278-tile Romania alive at tick 5003.

## 2. What bled troops (avoid / price correctly)
- Top troop stacks at tick 5003: Finland 1,559,097, Ukraine 1,355,966, Sweden 1,314,550, Slovakia 1,265,124, Kazakhstan 1,256,689, Sápmi 1,131,271, Norway 1,085,126. Human 3,359,577 = only 2.15x Finland. No head-on `attack nation-N` into 1M+ stacks; cap is 1,000,000 troops per attack intent (`MAX_ATTACK_TROOPS`), so you cannot one-shot them.
- Mid stacks that punish greed: Netherlands 997,310 / 85,748 tiles, Türkiye 962,610 / 35,545, Spain 937,276 / 79,324, Ireland 737,883, Algeria 776,993 / 104,302, Croatia 775,108. Attacking high-troop/low-tile nations (Türkiye 35k tiles but 962k troops, Serbia 30k tiles but 782k troops) bleeds with no tile payoff.
- Attacks without shared border retreat silent. Check `borders_human` before any `nation-N` / `tribe-N` order. Boat (`boatAttack x y troops`) is the only way to force a new border — validate water component; failed boats = lost tempo.
- Donations only land if allied (`donate_gold` / `donate_troops` silently refused for strangers). Never donate to buy peace unless `alliances[]` shows it.

## 3. When to strike (timing in this match's ticks)
- Decision cadence is fixed: `end_decision` = 50 ticks. Match ticks: 53,103,153,...5003. Plan in decisions, not ticks.
- Decisions 1-30 (ticks ~53-1503): pure expand + tribes. Do not open nation war; immunity + spawn spread make early nation attacks reject/waste.
- Decisions 30-70 (ticks ~1500-3500): pick ONE bordering sub-30k-tile nation (see list above) and finish it. Multi-front spreads the 2.5 tool-calls/decision budget (256 calls / 100 decisions here) too thin.
- Decisions 70-100 (ticks 3500-5003): this run stalled at 190k tiles with 43/52 nations still alive and winner null. You must convert troop lead (3.3M) into eliminations before tick 4000 — build `city`/`factory` early for economy, `defense-post` on the Finland/Estonia/Belarus/Russia axis (all 100k+ tiles: 123k/108k/108k/105k), then chain `warship`/`port` + `missile-silo`/`sam-launcher` if coastal.
- Build menu is exactly: city, defense-post, sam-launcher, missile-silo, port, factory, atom-bomb, hydrogen-bomb, mirv, warship. Upgradable only: port, missile-silo, sam-launcher, city, factory. Order upgrades by unit id; deletes have a grace period (unit stays listed briefly).

## 4. Never repeat
- Never end 100 decisions / 5003 ticks with 43 alive and winner null. 190k tiles + 3.3M troops is not a win on Europe Normal — push eliminations, not just tile lead.
- Never fight Finland (123,367 tiles / 1.55M troops), Georgia (110,492 / 760k), Estonia (108,884 / 604k), Belarus (108,270 / 478k), Russia (105,438 / 572k) simultaneously. They each out-tile all small nations combined.
- Never spam stale decisions: `end_decision expected` must be exactly `_decision+1`. One advance at a time; out-of-order = rejected.
- Never leave free kills: Germany 0/0, Syria 0/0, Romania 278, Northern Ireland 362 were still unclaimed value at the end. If `alive true` but tiles <5k and troops <200k (Jordan 1,562/178k, Latvia 28k/294k, Denmark 29k/375k), kill promptly instead of expanding past them.
- Never assume projection = full board: `tribes` total vs bordering `tribes_list`, `grid step>=4` downsample, nation labels `nation-1..52` stable by spawn order, `tribe-N` slots stable (dead keep slots). Use `overview` (pure query, no tick) before spending troops.
