True-view slice: tapes replay bit-for-bit in the real client (TDD, adapter-only)

Chain: worker tape (record.json) -> build_game_record.ts (GameRecord,
validated by production safeParse) -> real client joins as replay via one
stub endpoint (GET {apiBase}/game/{id}) -> ?spectate/gameserver not needed
for finished games.

Two findings, both fixed adapter-side, vendor untouched:
- Boot must mirror GameRunner line-for-line. It draws the human id from the
  seeded RNG before nations; our fixed id split every downstream RNG draw
  (same tiles, troops off ~20%). Worker now draws identically; human id is
  per-game (stable per game id, e.g. 945a9tlw) and recorded in the tape.
  Also mirrored: spawnNations condition, rail-cluster exec, full PlayerInfo
  args. Past tapes (old boot) play but diverge in outcome.
- Fixture maps (testdata plains) lack nations/additionalNations and have no
  client-side bins: replay boots but spawn lands on water. Fixture-only;
  real maps replay fine. (GameRunner also lacks the worker's `?? []`
  guard — production never hits it; not ours to fix.)

Evidence: tests/test_replay.py (live Europe game -> convert -> replay
through createGameRunner, exact tiles+troops; mutation-checked: wrong
expectations fail). Full gate 173 passed, ruff + ty clean.
