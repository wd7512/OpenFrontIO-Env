# Solo FFA playbook (Medium nations + many tribes)

## Ethos
- One order per 50-tick decision (5 s). A no-op decision is a lost decision: if nothing better, take free neutral border or build/upgrade a city. You win on tiles and troop ceiling, not on attrition.
- Survival gates everything: stay above 100 tiles (below that you are auto-conquered) and keep home troops above the strongest bordering non-allied rival while any wave is out.
- Land compounds: maxTroops = 2*(tiles^0.6*1000 + 50000) + 250k per city level; gold is 100/tick, so cities are cheap growth. Nations eat neutral/tribes almost every act tick — match that pace or fall behind.
- Prefer low-density bordering tribes and neutral land over nations; finish in one pass. A nation you half-kill regens, keeps its land and becomes a permanent enemy (attacking a player is -70 relation + auto-embargo on Medium).
- One war at a time: same-target land attacks merge, so concentrate. If a target survives a wave, do not repeat the same oversized wave — resize, boat it, or switch. Cancel vs a player burns 25%; vs neutral it is free, so neutral pushes are the low-risk default.

## When to act
- REFILL: a Medium nation acts every 55-70 ticks, a tribe every 40-80. Trigger is 50-60% of its max troops, reserve 30-40%, neutral-expand floor 10-20%. Below reserve it will not attack or retaliate against players (it still nibbles neutral).
- SPEND WINDOW: a rival whose troops drop ~15-25% with tiles steady just acted and sits at reserve, with almost nothing above it to throw until it refills (a large nation needs ~1-3 decisions). Strike then; if it named you, brace.
- NEUTRAL FIRST: on its act tick a nation with any adjacent non-nuked neutral expands there and returns, so it does not retaliate that tick. A target with a neutral border gives you a delayed counter; one without throws everything above reserve at you.
- FORCED RETALIATION: if one incoming attack is at least ~50% of your troops, stop expanding and send more than that attack at its attacker — a head-on attack cancels troop-for-troop at launch, deleting it, and your surplus advances. Counter the largest attacker: that is the one the rival aims at too.
- ALLIANCES: threat overrides relation — a Medium nation accepts you outright when your troops are >2.5x its, even at Hostile. It also accepts when Friendly, early (before ~tick 1900, ~70%), or similarly strong (~70-80% its troops or 80-90% its tiles), and rejects traitors; it stops around 4-6 allies unless you are a threat or Friendly. Tribes accept every request. Ask early and renew before the 3000-tick expiry.
- DEFENSE POSTS: driven by land attacks only (sourceTile null). On Medium, once the sum of its incoming land troops reaches 35% of its current troops it has a 50% chance per structure call (about every 20 ticks) to raise one post, max one; within 30 tiles attacker loss is x5 and capture rate /3. Keep simultaneous land pressure under 35% to avoid it, arrive with one wave that lands first, or open a boat front — a landing attack has sourceTile set and never counts toward the 35%. Build your own when a land front hits 35% (first post 50k).
- DOGPILE: incoming_troops at or above ~50% of a rival's own troops (and its troops no more than ~1.2x yours) means it is committed and counters weakly; Hard/Impossible nations pick it as their "victim". Hit it before an idle equal. At/above its troop count it is dying — race to border it for the carve-up rather than feeding it troops.
- BOATS: 3 free, ~1 tile/tick, only along straight cardinal water rays from your shore (boat_targets gives owner/troops/tiles). Use them for water-stalled fronts, neutral islands and bypassing a post/wall. Order many decisions ahead; never launch while home is thin.
- Only order attacks on bordering, non-immune players; a land attack with no shared border only embargos the target and returns your troops.

## Attack sizing (derive from D, T, density, terrain — never a fixed share)
- Per-tile attacker loss vs a player: L = 0.48 x clamp(D/A, 0.6, 2) x m + 0.52 x (D/T) x (m/100), where D = target troops, A = troops sent, T = target tiles, m = 80 plains / 100 highland / 120 mountain. Vs a tribe (Bot) m is x0.7 (56/70/84); a defense post on the tile multiplies m by 5. Very large defenders (~150k+ tiles) shave the first term by up to 30%.
- A = D is the knee; 1.3-1.7D is the efficient one-pass band. Below ~1D you cannot outrun the defender's regen, above ~1.7D you only strip your home. Regen while the front is open is about (10 + D^0.73/4) x (1 - D/maxD) per tick (Nation Medium x0.95), often tens to hundreds of thousands per decision.
- Neutral land: L is flat m/5 = 16/20/24 per tile regardless of A, and the front moves ~0.4 x frontier tiles/tick once A is at least ~6,600 on plains. Send about L x (tiles you mean to take) and keep the rest home; survivors return free when the front closes.
- Worked examples.
  - Tribe, 800 tiles / 50k plains: D/T = 62, so at A = 75k (1.5D) L ~ 36/tile and a full clear costs ~29k; 75k one-passes it, while a 15k probe pays ~2x per tile and dies.
  - Nation, 3,000 tiles / 200k plains, no post: D/T = 67, at A ~ 1.4D (280k) L ~ 54/tile, all tiles ~162k, so ~1.4D clears in one to two decisions. With a post L ~ 270/tile — boat it or skip.
  - Neutral, 1,000 plains tiles: 16/tile -> ~16k total; send ~16-25k across the frontier and leave the rest defending.
- Capture rate scales with frontier width and A/D, so attack along the widest shared border or add a boat front; a narrow contact stalls even with a huge army.
