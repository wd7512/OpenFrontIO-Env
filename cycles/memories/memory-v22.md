# Solo FFA playbook (nations + 400 tribes)

## Ethos
- One order per 50-tick decision (5 s). Spend it on the single best action: survive, finish a kill, take cheap land, or build. Half-measures lose; a dead player takes no land.
- Survival gates everything. Stay above 100 tiles (below that you are auto-conquered and carved up) and keep home troops above your strongest bordering non-allied rival. In FFA a Medium nation's `weakest` pick attacks only an enemy with fewer troops than itself, and its `hated` pick needs you Hostile and caps at 3x your troops, so the safe posture is strong, non-hostile and not dogpiled.
- Land drives growth: maxTroops = 2*(tiles^0.6*1000 + 50000) + 250k per city level, and regen scales with troops. Grab neutral border whenever safe; convert surplus gold (100/tick) into cities (125k, 250k, 500k...).
- One war at a time; same-target land attacks merge, so concentrate force. Finish or don't start: canceling a player attack or recalling a boat burns 25%, but a front that closes naturally returns survivors free.
- Attacking a nation drops relation -70 and auto-embargoes it (auto-rejecting your alliance requests), so it creates a lasting enemy. Prefer neutral land and tribes; nations eat tribes first too.

## When to act
- REFILL: a Medium nation acts every 55-70 ticks, a tribe every 40-80. Trigger is 50-60% of its maxTroops, reserve 30-40%, and its neutral-expand target only 10-20%; it attacks players only above trigger, else ~1-in-10 cycles.
- SPEND WINDOW: a rival whose troops fall ~15-25% with tiles steady just acted; it sits at reserve and won't name a fresh player target until it refills to trigger (about 1-3 decisions for a large nation). Strike then, or brace if it chose you.
- NEUTRAL FIRST: on its act tick a nation with any adjacent non-nuked neutral land expands there and returns; it does not retaliate that tick. It hits adjacent tribes next (4x their troops), then retaliates. A target with neutral border has a delayed counter; one without gives you everything above reserve.
- COUNTER: on its act tick it sends everything above reserve at its largest non-bot incoming attacker. Head-on attacks cancel troop-for-troop (larger deletes the smaller, remainder advances). To erase an incoming X, send > X at that attacker, and expect a full counter if it still holds above reserve. If your incoming_troops >= ~50% of your troops, stop expanding and cancel the largest attacker with more than it sent.
- ALLIANCES: accept when you are the threat (your troops > 2.5x its - threat is checked before relation), when relation is Friendly, early (before ~tick 1900, ~70% on Medium), or when similarly strong (~70-80% of its troops / 80-90% of its tiles). It rejects below Neutral, traitors, and after ~4-6 allies. Ask early, stay Friendly, never attack an ally, renew before the 3000-tick expiry.
- DEFENSE POSTS: a defender builds one when the sum of your LAND attacks (sourceTile null; boat landings excluded) reaches >= 35% of its current troops. Medium: 50% per call, max 1, ~2-3 calls per attack interval; within 30 tiles you lose ~5x and capture ~3x slower. Keep each probe under 35% of its troops, commit one decisive wave accepting the wall, or open a boat front (the landing skips the trigger, but an existing post still applies). Build your own post on a threatened front once incoming land attacks reach 35% of your troops; the first costs only 50k.
- DOGPILE: a rival with incoming_troops >= 50% of its own troops and troops <= ~1.2x yours is already committed and counters weakly - hit it ahead of an idle equal.
- BOATS: up to 3, free, ~1 tile/tick, launched at a boat_targets tile (first landfall on a straight water ray, with owner/troops/tiles). Use them where the land border is water or a post/wall has stalled the front; order early, since transit costs many decisions, and never launch while home is exposed.
- Only hit bordering (borders_human), non-immune players; an attack without a shared border retreats silently.

## Attack sizing (derive from D, T, density, terrain - never a fixed share)
- Per-tile attacker loss vs a nation: L = 0.48*clamp(D/A, 0.6, 2)*m + 0.52*(D/T)*(m/100), with D = target troops, A = sent, T = target tiles, m = 80 plains / 100 highland / 120 mountain. Vs a tribe (Bot defender) multiply L by 0.7 (m 56/70/84). A defense post multiplies m by 5, so L x5. D/A = 1 is the knee; at A = D/2 the clamp caps the first term.
- Taking all T tiles costs ~T*L plus the defender's regen (10 + troops^0.73/4 per tick, ~50-80k per decision at 100-200k). The efficient one-pass band is A ~ 1.3-1.7D; below ~1.0D you can't finish before it regrows, above ~1.7D only speeds capture. Never send so much that home drops under your strongest bordering rival's troops.
- Neutral land: L is flat 16/20/24 per tile whatever A, and the front advances ~0.4*frontier tiles/tick on plains once A >= ~6600. Send about L * (tiles you mean to take), not your whole army; survivors return when the front closes (TN cancel is free).
- Worked examples.
  - Tribe, 800 tiles / 50k plains: D/T=62, m=56 -> L ~ 36/tile at A=1.5D, full clear ~29k; a 75k push one-passes it, a 15k probe pays ~2x/tile and dies.
  - Nation, 3000 tiles / 200k plains, no post: D/T=67 -> L ~ 66/tile at A=D, ~55 at A=1.4D; all tiles absorb ~165-200k plus regen, so send ~1.3-1.5D and finish in 1-2 decisions. With a post L x5 (~330/tile) - boat it or skip.
  - Neutral, 1000 plains tiles: 16/tile -> ~16k troops total; send ~16k across the frontier and keep the rest home.
