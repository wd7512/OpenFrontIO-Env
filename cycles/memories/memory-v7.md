# Strategy Notes — Next Solo Europe Run (52 nations + 400 tribes, Easy, Normal FFA)

Source match: `live_result.json` solo, 164/200 decisions, 8203 ticks, winner=null, returncode=1. `record.json` ENGINE01 Europe Normal / 52 nations / bots=400. Human survived mid-pack, did not win.

## Final score that matters
- Human: 59,651 tiles / 869,831 troops (alive)
- Dead by tick 8203: 22/52 nations (Georgia, Switzerland, France, Belgium, Bosnia, Serbia, Israel, Netherlands, Syria, Austria, Lithuania, Türkiye, Portugal, Czechia, Morocco, Wales, Bulgaria, Andorra, Slovakia, Romania, Latvia, Germany). Someone is eating — you were not eating fast enough.
- Top that killed the win: Ukraine 249,359 tiles / 5,030,195 troops (4.18x your tiles, 5.78x your troops), Belarus 215,114 / 1,813,396, Kazakhstan 187,107 / 1,030,773, Spain 144,380 / 1,845,892, Iraq 138,729 / 2,302,536, Hungary 131,378 / 1,524,727, Italy 129,239 / 1,323,697.
- Your tier: tied Norway 59,653 tiles / 647,840 troops (you 59,651 — 2-tile gap = stalemate border, do not bash it), above Sweden 56,915 / 523,835, below Algeria 68,228 / 611,561, Monaco 65,469 / 487,570, Sápmi 84,340 / 776,291. To climb you need +25k tiles just to reach Ireland 96,261 / 1,443,466.
- Soft tile targets alive at end: Scotland 222 / 183,552, Lebanon 245 / 201,594, Poland 321 / 206,788, Greece 910 / 234,500, Northern Ireland 932 / 231,414, Denmark 2,484 / 342,388. All tile-weak but holding 180-340k troops — hit only one at a time with local superiority, never Ukraine/Belarus head-on.

## What won tiles here (do more)
- `expand` (attack null/TerraNullius) is the only safe early growth on a 400-tribe board. Tribes are Bot-type free land if `borders_human=true`.
- 50 ticks per decision (`session.py DECISION_TICKS=50`). 164 decisions = 8203 ticks. Growth compounds per tick — every idle decision costs ~50 ticks of income. This run averaged 2.66 tool calls/decision (436 calls / 164 decisions). Decide, order, end decision; do not over-query.
- Only bordering tribes are listed in projection (`tribes_list`), but any `tribe-N` is orderable via worker. Use the flag as your allowlist.

## What bled troops (stop)
- Attacks without shared border retreat silent (`session.py`: distant tribes unactionable). No error, just lost tempo/troops. Always check `borders_human` before `nation-N / tribe-N`.
- Spawn immunity + shared-border check decide if an order lands (`session.py order_attack`). Rejected early-game nation hits = wasted orders.
- Donations to strangers refused silently — engine only lets friendly/allied receive (`order_donate_gold/troops`). Never gift to non-ally.
- Boats: engine validates destination tile (`TransportShipExecution`); out-of-water/component fails. Warship patrol only lands on water in same component. Check `width/height` bounds first.
- Builds: engine validates gold/cost/tiles; structures need owned land, nukes take target tile, warships need water access. Acceptance != landing. Upgradable only: port, missile-silo, sam-launcher, city, factory. Delete has grace period (stays listed briefly — do not double-delete).

## When to strike
- Early (ticks 53-1000, decisions 1-20): pure `expand` + bordering tribes. 400 tribes = fastest uncontested tiles before nations consolidate.
- Mid (ticks ~2000-4500): pick ONE sub-3k-tile survivor (Scotland/Poland/Lebanon/Greece/N.Ireland/Denmark list above). Need >250k local troops before committing — they all banked 180k+.
- Never: Ukraine (5M), Belarus (1.8M), Spain (1.84M), Iraq (2.3M), England 49,317 tiles / 2,065,000 troops (dense elite) until you are >150k tiles + 2M troops. Norway-tie lesson: if tiles equal for >10 decisions, break off and expand elsewhere.
- Diplomacy on AI schedule: `allianceRequest` answered late/never. Do not wait for it; embargo/donate only after allied.

## Never repeat
1. 164/200 stop with winner=null — did not close. Do not stall at ~60k tiles mid-pack; force a kill on a <1000-tile nation before tick 4000 or you get outscaled (top went 200k+).
2. Do not order `tribe-N / nation-N` without `borders_human=true` — silent retreat.
3. Do not donate gold/troops to non-allies; do not spam alliance/embargo expecting instant reply.
4. Do not boat/warship to unvalidated tiles; do not build city/factory on unowned land or warship without water.
5. Do not burn 400+ tool calls on queries — 1 recon + 1 order per 50-tick decision is enough. Cost here was $0.00207 with 1,014,641 cache reads; wall 1724s for 8203 ticks — tempo matters more than micro.
