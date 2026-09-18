# Playbook — Solo FFA vs Many Nations and Tribes

## Ethos
War is an exchange rate, not a mood. Troops sitting at your cap earn nothing; land and cities raise the cap. Only battle converts one into the other — so grow continuously, then spend in decisive bites. Take cheap land the moment it is available, commit overwhelming force only to fights you mean to finish, and never let a blocked frontier, a stalled push, or a lost exchange turn into a quiet army. You have the highest troop ceiling in the game; time and growth are on your side if you don't trade them away.

## Growth is the win condition
- Cap = 2*(tiles^0.6 * 1000 + 50,000) + 250,000 per completed city level. One city level equals ~3,100 tiles of cap, so past the opening land grab cities dominate growth.
- Land has sharp diminishing returns: doubling your cap from land alone needs ~3.2x the tiles. Chase cities, not tiles.
- New cities double in price (125k, 250k, … capped at 1M) while gold accrues ~100/tick (~1000/s). Bank toward the next city, and once new cities cap out, upgrade the ones you have.
- Regen = (10 + troops^0.73/4) * (1 - troops/cap): fast when low, ~zero at cap. Spending down in an attack is good; hoarding at cap wastes your only compounding resource. Pause and refill after a big spend.
- You out-scale everyone: on Medium, nations get 0.75x cap and 0.95x regen, tribes 1/3x cap; you get 1.0x. Avoid any war that trades that edge away for no lasting land.

## Neutral expansion
- Neutral tiles are flat cost — ~16 plains / 20 highland / 24 mountain each — regardless of how many troops you send. Stack size only changes sweep speed (a few thousand sweeps fast; a huge stack slugs along at the floor). Size to the frontier, not the bank; survivors refund free when the border runs out.
- Tiles gained per tick scale with the length of your border, so expand along a broad front. If expand orders stop gaining tiles the frontier is gone: stop probing and switch axes.

## When a fight is worth it
- Against a player, per-tile attacker loss is clamp(defenderTroops/yourTroops, 0.6, 2) * terrainMag * 0.8, blended with a density term. terrainMag: plains 80, highland 100, mountain 120.
- The clamp is the whole game. At half the defender's troops you pay the 2.0 maximum; at parity 1.0; at ~1.7x you reach the 0.6 floor and extra troops stop cutting cost. Bring at least ~1.7x the defender's current total troops, and don't bother bringing 5x.
- Density matters: a sprawling empire is cheap per tile; a small nation massed on a few tiles is expensive per tile. Avoid grinding a cornered, troop-dense nation.
- A defense post within range 30 multiplies the defender's cost x5 and slows you x3; fallout is similar. Attack plains edges and undefended borders, go around, never through.
- Tribes are the cheap target (mag x0.7, 1/3 cap); nations cost more and regrow between strikes; neutral land is cheapest of all.
- Past ~100k tiles your own attacks weaken (loss up, speed down). At that scale prefer cities, consolidation and defense over conquest.

## Committing, cancelling, finishing
- The engine default for an attack or a boat is 20% of troops. Treat it as a benchmark to beat, not a plan: size the order deliberately and always keep a home reserve — zero tiles is elimination.
- Same-target land attacks from your border merge; opposing attacks cancel troop-for-troop; boat attacks never merge.
- Manually cancelling a player attack, or recalling a boat, kills 25% of the force still committed. An attack that simply exhausts its border, or never lands (no shared border, immunity, friendly), refunds survivors free. Scout before committing, then let a spent attack run out — never panic-cancel. A several-hundred-thousand-troop attack aborted on a whim is a lost army slice for nothing.
- Finish what you start: a player reduced below 100 tiles is auto-conquered and their land distributed. Drive a target under 100 or don't begin. Don't grind the same target for hundreds of ticks without finishing, and don't spread force across five targets at once.
- Fight one war at a time and keep the rest of the border quiet.

## Boats (the second front)
- At most 3 concurrent, zero gold, default 20% load. A landed boat instantly becomes a land attack from the beachhead with no second troop charge; boats do not merge with land attacks.
- This is the cheapest way around water and around a fortified or blocked frontier. Aim at the listed reachable shores; a no-water-path or friendly send refunds fully, an arrival on your own land refunds minus 25%.
- Size the boat to win the shore AND survive the counter — a beachhead you cannot reinforce is a donation. Then reinforce it with ordinary land attacks from the new shore rather than dumping more one-way boats. Loading a boat with a huge share of your army is the same over-commitment error as a giant land attack.

## When expansion stalls
- Rotate axis in order: bordering weak tribe -> transport to a listed neutral/weak shore -> cities and defense posts behind the line -> strike a neighbor already at war.
- Do not answer a blocked frontier by throwing ever-larger armies at the strongest neighbor. Do not declare on a nation you neither border nor have landed beside — with no adjacency the order simply refunds and burns a decision.
- Do not turtle: a defense post makes your border brutal but does not grow your cap. Every quiet turn should still buy a city or open a front.
- If troops and tiles fall together on an axis, disengage that axis. Never reinforce failure.

## Diplomacy
- Attacking a player auto-embargoes them, voids pending alliance requests both ways, and tanks relations (-70 Medium / -80 Hard). Pick your one enemy deliberately; never request an alliance with someone you may later attack.
- Ally the neighbor you won't fight and concentrate elsewhere. Relations recover slowly.

## Discipline
- Every decision should do something: expand, build or upgrade a city, or act on a front. Idle decisions are the one unrecoverable loss — the run ends with decisions unused if you spend them waiting.
- The early spawn immunity is short (~50 ticks); use it to grab neutral land and start your first city rather than poking nations.
