Play one default solo game: your human vs 400 tribes and 52 nations on full Europe, bots at {difficulty} difficulty.

Tools (game MCP only):
- game_start_solo_game with difficulty "{difficulty}" (no other arguments), then game_get_overview.
- game_get_overview: the state. Human, nations, tribes_list (only bordering tribes are attackable), boats, units, alliances, attacks, winner.
- game_order_attack with target 'expand' plus troops, or a tribe-/nation-id plus troops.
- game_order_build / game_order_upgrade_unit, game_order_embargo, game_order_cancel_attack.
- game_end_decision with the next decision integer advances 50 ticks.

Loop every decision: game_get_overview, then orders, then game_end_decision. {max_decisions} is a hard ceiling, not a target.
Keep playing until you WIN (winner is you) or DIE (you are eliminated) — that is the only acceptable end. When the match ends (win, elimination, or the decision ceiling), write your final report and stop calling tools.
Then stop. Report tiles and troops per phase, tribe kills, when contact happened, whether nation attacks landed, what you built, and the winner if declared.
{memory_block}
