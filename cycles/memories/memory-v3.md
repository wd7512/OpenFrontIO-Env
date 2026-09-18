# NEXT PLAYER NOTES — Europe Solo FFA (same format)

Format taped: Europe Normal full-res, Singleplayer FFA, Easy, 52 nations + 400 tribes/bots, `donateGold=false donateTroops=false`, seeded random land spawn. 100 decisions x 50 ticks = 5003 ticks total. Spawn tick 53, then 103,153...5003. Winner: null. Wall 950.5s / 947573ms, 276 tool calls, cost 0.00232.

Final score this match (human "Smoke", alive):
- human: 52492 tiles / 267678 troops
- 8 nations dead with 0 tiles: Switzerland (6107 troops left), France (10086), Syria (26605), Austria (23322), Czechia (8280), Wales (44110), Andorra (25172), Germany (0/0 — only fully dead stack)
- human troop rank near-bottom: only Scotland (322 tiles/40305), Bosnia (252/20429), N.Ireland (584/129709), Libya (308/183930) smaller; next above human is Poland 17310/258893, then Denmark 23888/287305. Everyone else 300k-1.69M.
- tile rank mid-low ~20th/53. Do NOT call this a win — survived, did not contend.

What the board looked like at 5003:
- >100k tiles + >1.4M troops tier — do not touch head-on: Finland 130958/1600444, Kazakhstan 118431/1529447, Russia 115124/1512325, Belarus 107948/1471893
- Next killers: Sapmi 97702/1294625, Algeria 99180/1122072, Sweden 77483/1282904, Estonia 88844/554479, Tunisia 85359/883466, Georgia 72983/826362, Monaco 73391/1638113, Egypt 61185/1695856, Ireland 32252/1335078, Iraq 67724/1129784, Ukraine 66650/1103608, Norway 54129/1116924
- Softest alive targets if you must hit a nation: Bosnia 252/20429, Scotland 322/40305, Libya 308/183930, N.Ireland 584/129709, Lebanon 12823/317266, Morocco 19676/280398. Prefer dead-nation vacuums and tribe land over any 500k+ stack.

WHAT WON TILES:
- `expand` (null-target attack into TerraNullius/tribe land) is the only safe growth to 50k+. Nation attacks stall against 1M+ stacks.
- Tribe clearing when `borders_human=true`. Only bordering tribes are listed in overview — distant tribe-N stays orderable but attacks without shared border retreat silent. Check projection after every order.
- Boat landings to leapfrog: engine validates tile, adapter only checks bounds. Use for empty coast, not into Finland/Kazakhstan cores.

WHAT BLED TROOPS:
- Trading with 600k-1.6M nations (Egypt 1.69M, Monaco 1.63M, Finland 1.60M, Kazakhstan 1.52M, Russia 1.51M). Human ended 267k — ~6x smaller. Any sustained attack order there just drains.
- Over-ordering: 276 tool calls for 100 decisions (2.76/decision). Every rejected/duplicate attack, boat, build still tapes and costs ticks. This match burned ~643k tokens (636401 cache-read, 3710 in, 1234 out, 2149 reasoning).
- Donates to non-allies refused silently. Embargo/alliance/diplo to strangers does nothing until allied.

WHEN TO STRIKE:
- Decisions 1-30 (ticks 53-1503): only expand + tribes. Nations immune early and you have no border info — nation hits rejected.
- Decisions 30-70: keep expanding to ~40-50k tiles, build city/factory/port core. Only snipe 0-tile corpses (Germany-type) or sub-50k-troop border nations (Bosnia/Scotland-type).
- Decisions 70-100: do NOT start a new front. This match proved 52k tiles holds alive to 5003 with no winner — late nation war just drops you from 267k toward <100k and invites Finland/Russia-tier retaliation. Defend, consolidate, boat-poke empty land only.

NEVER REPEAT:
- Never attack a 500k+ nation head-on with 267k total. Max attack param is 1000000 but you never had it — don't empty the home garrison.
- Never spam non-bordering nation-N / tribe-N: silent retreat, wasted decision.
- Never donate gold/troops unless `alliances` shows them friendly — engine friendly-only.
- Never expect alliance answers same decision — recipient AI answers on its own schedule or never. Don't wait; keep expanding.
- Never build outside owned land or warship without water access — engine rejects, adapter only checks 0<=x<width. Same for nukes (atom/hydrogen/mirv need target tile) vs structures.
- Never upgrade non-upgradable: only port, missile-silo, sam-launcher, city, factory upgrade. Defense-post, silo nukes, warship do not.
- Never delete-and-expect-gone: delete has grace period, unit stays listed briefly.
- Never warship-retarget onto land: must be water in same component.
- Build menu is exactly: city, defense-post, sam-launcher, missile-silo, port, factory, atom-bomb, hydrogen-bomb, mirv, warship. Anything else rejected pre-engine.
