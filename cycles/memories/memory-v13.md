# Playbook — Solo FFA vs Nations + Tribes

## Ethos
Grow the economy; treat war as a rare, decisive act, not a habit. Neutral land is cheap, cities set your real army ceiling, and troops tied up in an attack are troops not regenerating. Attack only when the tiles are free (neutral, weak bots) or when you can overwhelm the defender outright. A bigger army is not a plan: trickling wave after wave into a strong neighbor is the fastest way to lose everything.

## Grow before you fight
- Neutral land is the only cheap tile source. Attacker loss is flat per tile — about 16 on plains, 20 on highland, 24 on mountain (terrain mag / 5) — regardless of force size, so size the force to the border, not the bank. Extra troops in an expand just sit locked in the attack.
- Army ceiling is `2*(tiles^0.6*1000 + 50000)` — a ~102k floor at one tile, with sharply diminishing returns from land. Each completed city level adds 250,000, so cities, not raw acreage, are the growth engine. Build them on safe interior tiles whenever gold allows.
- Gold, not time, limits structures: income is ~100/tick (~1000/sec), and city costs run 125k, 250k, 500k, 1M... — roughly one city level per couple of minutes. Never queue builds you cannot pay for; a failed build wastes a decision.
- Regen is `(10 + troops^0.73/4) * (1 - troops/max)`: fastest from a low count, almost zero near the cap. After any big spend, stop attacking for several decisions and let the bar refill; attacking while full throws away banked regen.
- Early is the only truly free expansion window. Nations and weak tribes start only marginally ahead of you; take open land before their borders harden.

## When attacking a player is worth it
- Conditions: you share a border, the target is out of spawn immunity, and you can overwhelm. Per-tile loss scales with `defender.troops / your committed troops` (clamped 0.6–2.0) plus their troop density — so commit at least the defender's total troops, ideally ~1.5–2x. Below about half their troops you pay the maximum loss and crawl; at/above their strength you hit minimum loss and top conquest speed.
- Do not feed a nation repeated large-but-not-overwhelming waves. It regrows between strikes, the exchange bleeds you, and it eventually counterattacks with interest. Pick one decisive war or avoid the border.
- Tiles held by bots/tribes cost ~30% less to take (attacker loss x0.7) and bot ceilings are one-third of a human's — bordering weak tribes are the correct tile bank. Nations are ~1.4x more expensive and usually not worth grinding.
- Terrain and structures: defense posts give the defender x5 defense and x3 slowdown within range 30; mountains/highlands cost more and move slower; fallout multiplies your cost up to ~5x. Attack plains edges, avoid the rest.
- Large holders (>~100k tiles) take reduced loss, and your own size slows your conquest past ~100k tiles. Late game, grinding a leader's front is a trap — take small pockets or grow cities instead.
- Finishing blow matters: any player reduced below 100 tiles is auto-conquered and their tiles are distributed. Either drive a target under 100 or do not start the war; stopping at a few thousand tiles buys nothing.

## How much to commit
- The engine default for an attack or a boat is `troops/5` (20%). Treat it as a ceiling, not a target.
- For neutral expands, commit only what keeps the front moving; per-tile cost is fixed, so a small force takes the same tiles for less exposure.
- For player wars, only commit when you can send at least the defender's total troops. If you cannot, do not order the attack that decision.
- Always keep a home reserve. Zero tiles is elimination, and troops in hand are worthless once the land is gone.
- One order per target. Same-target land attacks merge and opposing attacks cancel troop-for-troop, so a second order adds nothing; ordering two targets at once halves both efforts. Boat attacks do not merge.

## Retreats and failed orders
- Cancelling a player attack or recalling a boat kills 25% of the committed force. A neutral expand that simply runs out of border returns survivors free. Rule: never order what you will cancel — verify border, immunity, terrain, and density first, then let the 50-tick decision window work.
- An order that cannot land (no shared border, friendly target, spawn immunity) still consumes the decision window and does nothing. Scouting the target before ordering is free.
- Do not ping-pong orders every decision; each re-order resets the attack and wastes troops to retreat tax or lost progress.

## Transport ships
- Boats are a crossing tool, not a routine attack: at most 3, each defaults to 20% of troops, and a landed boat begins a land attack with no second troop charge.
- Sailing home costs the 25% tax; a boat with no water path refunds in full; a boat whose destination becomes water auto-retreats. A committed crossing is the whole cost, so size it to take and hold the beachhead.
- Only sail to a listed `boat_targets` shore, and prefer neutral or weakly held land behind it. A boat into a fortified beach is a donation. If no landing is listed, there is no water route — do not force it.

## Breakout when land expansion is blocked
- If your expand orders stop gaining tiles, the neutral frontier is gone. Stop probing it with repetitive small orders.
- Rank the exits: (1) a bordering weak tribe, (2) a transport ship to an offered neutral/weak shore, (3) build cities and a defense post and regrow behind your line, (4) wait for a neighbor war and take a cheap pocket.
- Do not "solve" a stuck frontier by throwing an ever-larger army at the strongest neighbor — the engine punishes exactly that. If tiles fall while troops fall, the line is lost: change axis, hold, and regrow rather than doubling the stake on the same border.
- A quiet border is an asset. Do not war and woo the same neighbor: attacking tanks relations and embargoes you, so a later alliance request to that nation is refused and the decision is wasted. Keep one front at a time and ally where you are not fighting.
