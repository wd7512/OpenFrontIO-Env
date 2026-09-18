# Strategy Notes — Next Player, Same Format

Format (from record.json / session.py): Europe Normal, FFA Singleplayer, Hard, 52 nations, 400 bots/tribes, no infinite gold/troops, no instantBuild, randomSpawn false. 50 sim ticks per decision (DECISION_TICKS=50).

## What happened here (concrete)
- Result (live_result.json): human 0 tiles, 6084 troops after 38 decisions / 1903 ticks (ticks 53..1903). winner: null. Duration 332s, 112 tool calls (~3/decision). max_decisions was 200 — run ended early, eliminated.
- All 52 nations alive at end. Human is the only 0-tile player.
- Scale needed to live on this board:
  - Near-dead: Serbia 154 tiles / 39873 troops; Egypt 2021 tiles / 149554 troops.
  - Weakest real survivors: Ireland 10534 tiles / 415723, Wales 15096 / 449503, Denmark 15594 / 122946, England 16074 / 512780, Hungary 16698 / 555355.
  - Mid-pack: 24k-48k tiles (Germany 23922, Croatia 24007, Netherlands 24401, Switzerland 25466, Italy 27315, etc.) with 500k-1M troops.
  - Leaders: Finland 79077 / 925252, Belarus 78685 / 1666059, Tunisia 75741 / 1671856, Russia 71711 / 665465, Sweden 70996 / 1235564, Iraq 70060 / 1163255, Ukraine 69252 / 1363317, Georgia 67496 / 1242114, Kazakhstan 63658 / 1134452, Algeria 62070 / 929850, Morocco 61443 / 1290085.
- Human 6084 troops = ~1/20th of Denmark (lowest survivor at 122946) and ~1/270th of Tunisia/Belarus (~1.6M). 0 tiles vs 15k minimum for a weak hold.

Takeaway: on Europe Hard 52+400 you must be at 15k+ tiles and 400k+ troops to even hold; 60k+ tiles and 1M+ troops to contest. This run never got on that curve.

## What wins tiles
- `expand` (attack null -> TerraNullius) is the only safe early growth. Do it every decision until border pressure forces otherwise. Nations in this match all banked 20k-79k tiles mostly off neutral/tribe land, not each other — all alive at tick 1903.
- Tribes (400 on board): only bordering tribes are listed in overview, but any tribe-N is orderable (worker keeps full list). Clear bordering tribes with explicit tribe-N attacks when you share a border; they are tile banks.
- Keep 1 live attack at a time where possible; engine reports attacks/retreating in snapshot — check it before re-issuing.

## What bled troops (avoid)
- Attacking nations early. Production rules decide if the order lands (spawn immunity, shared border). Non-bordering attacks retreat silent — pure wasted decision + troops. Session only lists bordering tribes for a reason.
- Ending with 6k troops means fighting anything above Egypt/Serbia weight was suicide. Never trade into 500k-1.6M stacks (Greece 1328539, Norway 1552198, Lithuania 1059120, Turkiye 1013785, etc.). You lose the math 100:1.
- 112 tool calls for 38 decisions suggests thrash/re-orders. Each decision is 50 ticks of compounding — idle or cancelled attacks bleed while neighbours expand.

## When to strike
- Decisions 1-10 (ticks ~50-500): only expand + bordering tribes. No nation-N. Build economy (city/factory/port per build menu) on owned land.
- Decisions 10-25 (ticks ~500-1250): keep expanding; hit tribes; build defense-post / SAM if bordering a grower. Only consider nation-N when you have 15k+ tiles, 300k+ troops, shared border (borders_human flag), and target is weak/distracted (Egypt/Serbia profile: <5k tiles, <200k troops).
- Decisions 25+: do not start a nation war unless you are already mid-pack (30k+ tiles). In this match nobody died by tick 1903 — Hard nations turtle and outscale; late solo aggression without 1M troops = elimination (this run: 0 tiles).

## Never repeat
1. Never finish early game under 10k tiles. Denmark/England survived at ~15-16k; this run had 0. If not at 10k+ by decision ~15 (tick ~750), you already lost — restart the expansion line, don't pivot to nations.
2. Never order nation-N or tribe-N without borders_human=true and immune=false. Engine rejects/silent-retreats; you burn the 50-tick window.
3. Never sit on 6k troops in the open. If troops <100k while neighbours are 500k+, do not attack — expand/consolidate/build only.
4. Never waste decisions on distant tribes/nations not in overview. Only bordering tribes listed = only actionable ones.
5. Never ignore units/boats/alliances fields: under_construction, retreating, incoming alliance requests decide whether your last order even landed. Re-query (overview) before stacking orders.

Record tape (record.json) was single-line truncated in review, so order-by-order timing above is inferred from tick/decisions + engine (worker.ts) + adapter (session.py), not per-turn intents. Next runner: preserve record.json with line breaks or per-turn JSONL so exact bleed tick can be named.
