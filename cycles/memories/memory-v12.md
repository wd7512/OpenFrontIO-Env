# Playbook — Solo FFA vs Nations + Tribes

## Ethos
Survive by economy, not by trades. Tiles raise the troop ceiling, cities raise it faster, and troops regenerate fastest when held well below the ceiling. Every attack spends troops permanently; only attack when the tiles or the kill buy back more than they cost. One clean order per decision, then let ticks settle before re-ordering. Never feed a larger stack.

## Grow first
- Expand on neutral land before touching any player. Neutral is the only cheap tile source: cost is flat per tile (plains cheapest, mountain dearest), no defender stack to trade into.
- Bordering tribes are the second tile bank. Only listed bordering tribes are actionable; an attack with no shared border retreats without effect.
- Build a city on safe owned land as soon as expansion yields a core. Ceiling is sublinear in tiles but +250k per city level, so cities compound while raw land does not. Never run a long game on land alone.
- Regen scales with `1 - troops/max`: a full army barely regrows. After any big spend, pause attacking and let the bar refill.

## When attacking a player is worth it
- Only hit a target you border, that is out of spawn immunity, and whose troop density (troops/tiles) you can afford. Defender density is what kills you, not raw size.
- Prefer weak density and small stacks; never trade into a stack several times yours. Defender losses are density-based, attacker losses scale with defender-troops/attacker-troops (clamped), so attacking up is always a losing trade.
- Avoid targets behind defense posts (roughly 5x cost, 3x slower), mountains/highlands, and fallout. Plains into an exposed edge is the only fair fight.
- Very large holders get a defensive discount and very large attackers get a penalty past ~100k tiles: late-game land grabs slow down for everyone. That favors picking small pockets over grinding a leader's front.
- Opposing attacks cancel troop-for-troop and same-target land attacks merge: one order per target is enough. Stacking two orders on one target in one decision adds nothing.

## What share to commit
- The engine default is one-fifth of held troops per attack and per boat. Treat that as the maximum normal commit, not the minimum.
- Commit less when probing or expanding: neutral cost is per tile, so size only sets speed (capped per tick). A small expand force takes the same tiles for fewer troops committed; keep the rest regenerating.
- Never empty the account on one player attack. Attacker loss scales against committed troops, so an undersized force bleeds per tile and stalls, but an oversized force risks the whole game on one border. If the target's density is near or above yours, do not attack at all.
- Keep a home reserve always. Zero tiles with a few thousand troops left means elimination; troops in hand defend nothing once land is gone.

## Why retreats are costly
- Cancelling a player attack (or a boat that sails home) burns 25% of the committed force. Cancelling a neutral expand is free.
- Attacks with no border, on friendlies/ allies, or into immunity retreat without effect and still cost the decision window.
- Rule: do not order what you will cancel. Verify border, immunity, and density before ordering. After ordering, let the 50-tick decision window work; re-check before adding more. ~3 orders per decision without settling is how small armies evaporate.
- Boats with no water path refund in full; boats that turn home pay the 25%. Aim boats only at offered landing spots on a water-only line.

## When transport ships help
- Boats are the breakout tool, not a routine attack. Use them when land expansion is sealed by water or by stronger neighbors, to reach neutral or weak land across water.
- At most 3 boats exist at once. Each defaults to one-fifth of troops. A landed boat starts a land attack with no second troop charge, so the sailing force is the whole cost.
- Only sail to reachable shores: if no landing is listed, there is no water connection — do not force it. Prefer neutral/weak landfalls over a fortified nation shore; a boat into a big stack just delivers troops to die.
- Do not recall boats casually: the return tax is the same 25%. Sail once, with a force sized to take and hold the beachhead.

## Breakout when land is blocked
- Stop feeding the blocking front. Consolidate, city up, hold below ceiling to regrow.
- Scan for the two exits in order: (1) bordering weak tribe for cheap tiles, (2) boat to neutral or thinly held shore across water. Hitting the strong blocker again is the losing move.
- If neither exit exists and you are small while neighbors are large, turtle: hold, regen, wait for a weak opening. A small force that keeps attacking leaders only feeds them.
- If tiles stay flat across several decisions while troops fall, the line is lost — change axes (tribe vs boat vs wait), do not double the stake on the same border.
