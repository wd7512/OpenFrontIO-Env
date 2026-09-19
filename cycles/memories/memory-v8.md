# Strategy Notes — Next Solo Europe Hard FFA Player
Format: Europe Normal, Singleplayer FFA, Hard, 52 nations + 400 tribes, seeded random land spawn, 50 ticks per decision. Last match: 44 decisions, 2203 ticks, 124 tool calls, ~305s. Ended human 0 tiles / 39627 troops, winner null, all nations still alive.

## What won tiles in this match
- Scale to survive is 80k-113k tiles. Top: Finland 113264 / 1746829, Belarus 104620 / 2112227, Russia 96748 / 1182563, Sweden 95690 / 1524065, Georgia 89886 / 1353267, Sapmi 74869, Kazakhstan 81358, Ukraine 80932, Tunisia 79064.
- Mid-pack safe zone is ~35k-65k tiles: Algeria 61962, Syria 59918, Turkiye 54720, Estonia 51635, Spain 48568, Bulgaria 46905, Andorra 45839, Poland 44188, Libya 42726. Below 25k you are prey: Scotland 18945, Israel 18858, Denmark 12765, England 11812, Ireland 10757, Hungary 7334.
- Dead walking is under 1000 tiles: Serbia 177 tiles / 17196 troops, Egypt 527 / 166233. Human at 0 tiles / 39627 troops proves troops without land are worthless — income is tiles.
- Troop density of winners: ~13-20 troops per tile (Finland ~15.4, Belarus ~20.1, Sweden ~15.9). Do not try to out-stack them without matching tile base. Match ended with Norway 1849585, Turkiye 1485931, Romania 1325765 as troop leaders — all had 36k+ tiles to fund it.

## What bled troops
- Holding 39k troops with 0 tiles = elimination. Troops do not defend without territory. Convert early troops to expand, not hoard.
- Attacking without shared border silently retreats and wastes the decision. Adapter only lists bordering tribes for a reason. Always check borders_human true before ordering nation-N / tribe-N.
- Spawn immunity blocks early nation hits. If immune true, the order will not land — expand instead.
- Boat attacks and long-range nukes / warships cost gold and troops the early economy cannot afford on Europe full-res. No evidence they saved the human here. Expand and city/factory economy first.
- Donations only work to allies. Gifting to strangers is silently refused — lost tempo.

## When to strike
- Decisions 1-10 (ticks ~53-503): expand only into adjacent neutral land every decision. Do not touch nations. Goal is to escape the under-25k death zone before crowding. With 52 nations + 400 tribes, neutrals go fast.
- Decisions 10-25 (ticks ~503-1253): keep expanding, add city then factory/port on owned land for income. Only hit bordering tribes when you locally outnumber them and borders_human is true. One attack order per decision, then let 50 ticks resolve before re-issuing.
- Decisions 25-40 (ticks ~1253-2003): pick ONE weak bordering nation under ~20k tiles with low troops per tile and immune false. Hit with overwhelming mass, then immediately expand to backfill. Never multi-front two nations at once in this crowd.
- After tick 2000: leaders are 90k+ tiles and 1M+ troops. Do not duel them head-on. Snipe dying smalls (Serbia/Egypt pattern) and consolidate. Human died by tick 2203 with zero tiles — late game without a 35k+ base is unwinnable.

## What to never repeat from ENGINE01
- Never end a decision without an expand or consolidation attack running while neutral land exists. Human stalled and got squeezed to 0 tiles while 50+ nations all survived to tick 2203.
- Never attack nation-N without checking alive, immune false, borders_human true in overview. Non-bordering attacks retreat silent.
- Never order tribe-N by guess — use only bordering tribes_list ids, but any tribe-N stays orderable so a typo still burns troops.
- Never save troops off-territory. 39627 troops with 0 tiles still counts as dead.
- Never fight winners early: Finland, Belarus, Russia, Sweden, Georgia all cleared 89k+ tiles by tick 2203. Early contact with them bleeds you for nothing.
- Never waste build orders on water/invalid tiles or unowned land — engine validates and rejects, costing a full 50-tick decision. Build only city / defense-post / factory / port on confirmed owned land, warship only with water access.
- Never spread tool calls thin: last run used 124 calls over 44 decisions (~2.8 per decision). Spend them on overview + one clean attack/expand + end_decision, not diplomacy spam. No alliances or embargoes won tiles here.
