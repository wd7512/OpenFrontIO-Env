# Europe Solo FFA — Strategy Notes for Next Player (same format)

Format this match (from record.json + session.py):
- Map: Europe Normal, FFA Singleplayer, Easy, 52 nations + 400 bots/tribes
- Spawn: seeded random land (europe full-res, spawn=None)
- Cadence: 100 decisions x 50 ticks = 5003 ticks total (ticks 53..5003 in live_result.json)
- Cost: 299 tool calls (~3/decision), 759s wall, winner=null, timed_out=false

Final score this match (live_result.json summary.final_human):
- Human "Smoke": 53,897 tiles, 364,874 troops at tick 5003
- No win. Game still open with 47/52 nations alive.

## Where that puts you
- Tiles ~16th of 53. Above you (15 nations): Tunisia 144,745, Finland 110,762, Kazakhstan 107,392, Belarus 106,903, Russia 106,580, Estonia 105,332, Sapmi 96,158, Italy 91,832, Ukraine 89,862, Georgia 86,377, Sweden 84,863, Spain 77,205, Andorra 77,132, Croatia 65,780, Poland 64,395.
- Just below you: Lithuania 51,370, Libya 44,159, Slovakia 42,603, Syria 42,911, Belgium 38,767, England 37,773, etc. You held mid-table.
- Troops poor: 364k vs leaders Kazakhstan 1,459,231, Sapmi 1,401,721, Finland 1,361,965, Ireland 1,335,489, Sweden 1,331,215, Norway 1,235,014, Norway/Russia/Italy/Tunisia all 1.1-1.2M. You are ~1/4 of a leader stack. Do not head-butt them.
- Dead (0 tiles) proving consolidation happens without you: Switzerland (3,684 troops left), Bosnia and Herzegovina (48,306), Austria (7,128), Wales (25,665), Germany (46,761). Five slots already cleared by others.

## What won tiles here
- Neutral/tribe expand scales on Europe Normal. 53k tiles is survivable to tick 5000 without a nation kill — it comes from steady `expand` (attack with null targetID -> TerraNullius in worker.ts) plus eating small tribes. Keep one expand order live almost every decision until ~40k tiles.
- 400 tribes means free bordering food. session.py only *lists* bordering tribes in `tribes_list` to save context (~45KB blowout if all 400 listed), but *any* tribe-N stays orderable via worker tribeIDs. If list is empty, you are not bordered — expand, don't force a distant tribe attack (it retreats silent, no border = no gain).
- Small nations stayed small to tick 5003 and are the only fair nation fights: Scotland 915 tiles / 106,015 troops, France 1,372 / 230,653, Northern Ireland 213 / 109,546, Latvia 4,153 / 194,104, Algeria 3,662 / 158,791, Albania 4,386 / 196,484, Hungary 9,956 / 388,869. Those are 200-4k tile pinatas. Take from this tier, not 60k+ tier.

## What bled troops
- Trading 364k vs 700k-1.4M nation stacks. Anyone above ~60k tiles in this tape also had 570k-1.4M troops (Georgia 766k, Poland 573k, Croatia 859k, Spain 661k, Ukraine 706k). Even a "win" vs them costs more than expand earns. Final troop gap proves it: you ended below 20+ nations.
- Distant/non-bordering attacks. worker.ts `attack` rides AttackExecution; without shared border it retreats silent but you still spent the decision + tool calls. session.py projects `attacks {id,target,troops,retreating}` — if retreating=true, cancel immediately via `cancel_attack`, don't reinforce.
- Boat/sea play without port/water-component check. `boat` -> TransportShipExecution, engine validates tile; `move_warship` only lands on water in same component. Failed boats = lost troops + lost decisions. Don't boat until you own coast + port and have a bordering-tribe-sized target (sub-5k tiles).

## When to strike
- Decisions 1-30 (ticks ~0-1500): only expand + bordering tribes. Nations are immune early and you need tile income to fund troop regen. Do not order nation-N before you border them (`borders_human` flag in overview) and before ~20k tiles.
- Decisions 30-70 (ticks ~1500-3500): pick ONE sub-10k bordering nation (from Scotland/France/N.Ireland/Latvia/Algeria/Albania tier if they border you). Hit with overwhelming troops, keep expand as second order. Never split across two nations — 299 tool calls in this match (~3/decision) shows split focus burns budget.
- Decisions 70-100 (ticks 3500-5003): only hit if target troops < 0.7x yours and tiles < 20k (e.g. Serbia 16,160/395k, Denmark 18,921/265k, Bulgaria 23,340/452k were the next tier up). Otherwise expand and bank troops. Leaders Tunisia/Finland/Kazakhstan/Russia/Estonia at 100k+ tiles are never correct targets from 53k/364k.

## Never repeat
- Never end at 364k troops on Europe solo. Top 10 all >700k; top 4 >1.3M. If overview shows you <50% of bordering nations' troops, stop nation attacks, full expand + build city/factory on owned land.
- Never fight uphill on tiles: attacking Poland 64k / Croatia 65k / Andorra 77k / Spain 77k from 53k loses on math alone. Concrete rule from this board: only attack nations with fewer tiles than you, ideally <10k.
- Never waste builds on unowned/water tiles or unupgradable units. Buildable here: city, defense-post, sam-launcher, missile-silo, port, factory, atom-bomb, hydrogen-bomb, mirv, warship. Upgradable only: port, missile-silo, sam-launcher, city, factory (engine decides). Build needs owned land + gold; nukes take target tile; warship needs water access. Acceptance != landing — check `units` + `under_construction` next overview.
- Never donate gold/troops to non-allies (engine silently refuses unless allied), never expect alliance answers same decision (recipient AI answers on own schedule or never). Don't embargo/break without a troop plan — it just paints you.
- Never let a Tunisia run free: 144k tiles / 1.16M troops won this lobby uncontested. If grid shows one nation >100k by tick 3000, you must either expand faster on the opposite edge or ally-chain its neighbors — solo-pushing it from mid-table fails.

Engine gotchas (worker.ts/session.py, not advice):
- `expand` = attack null. `nation-N`/`tribe-N` use stable numbering (nations in spawn order, tribes sorted then append-only, dead keep slots).
- MAX_ATTACK_TROOPS 1,000,000 per order. Cancel needs live `attack.id` / boat `unit.id`.
- `advance` is exactly 50 ticks/decision; stale `expected` rejected. `inSpawnPhase` must be false before attacks land.
- Grid sampling needs step>=4; legend H=human, T=tribe, ./space=water/land.
