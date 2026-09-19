"""Real-engine orders: expand (vs TerraNullius) and attack (vs nations).

No mocks: orders go through Executor.createExec (the same path live turns
take) into AttackExecution, and are observed via player.outgoingAttacks().

Production facts these tests pin:
- expand conquers adjacent neutral land, so human tiles grow;
- a nation attack with no shared border fizzles by design (AttackExecution
  retreats when refreshToConquer finds nothing) — the order is accepted and
  the engine stays healthy, but no attack persists;
- an attack ordered during nation spawn immunity (50 ticks) also fizzles at
  init (canAttackPlayer), so live orders belong after tick 50.
"""

from openfrontbench.engine import EngineWorker


def test_expand_conquers_neutral_land():
    with EngineWorker() as engine:
        started = engine.start(nations=1, difficulty="easy")
        assert started["human"]["tiles"] == 52
        engine.attack(target="expand", troops=5000)
        after = engine.advance(50)
        assert after["human"]["tiles"] > 52


def test_nation_projection_exposes_immune_and_border_flags():
    with EngineWorker() as engine:
        started = engine.start(nations=1, difficulty="easy")
        nation = started["nations"][0]
        assert nation["immune"] is True
        assert nation["borders_human"] is False
        grown = engine.advance(60)  # past the 50-tick nation spawn immunity
        assert grown["nations"][0]["immune"] is False


def test_winning_recipe_expand_to_contact_then_strike():
    """The campaign playbook, pinned at engine level: half-troop expands
    until tiles stall (contact), then half-troop nation strikes until the
    production win check fires. Union Alpha executed exactly this live and
    won at tick 503; the script must reproduce it deterministically."""
    with EngineWorker() as engine:
        state = engine.start(nations=1, difficulty="easy")
        human_name = state["human"]["name"]
        previous_tiles = 0
        for _ in range(15):
            troops = max(1000, state["human"]["troops"] // 2)
            engine.attack(target="expand", troops=troops)
            state = engine.advance(50)
            if state["human"]["tiles"] <= previous_tiles:
                break
            previous_tiles = state["human"]["tiles"]
        assert state["human"]["tiles"] > 3000  # contact, fronts met
        for _ in range(10):
            troops = max(1000, state["human"]["troops"] // 2)
            engine.attack(target="nation-1", troops=troops)
            state = engine.advance(50)
            if state["winner"] is not None:
                break
        assert state["winner"] == human_name


def test_nation_attack_without_border_fizzles_by_design_but_engine_survives():
    with EngineWorker() as engine:
        engine.start(nations=1, difficulty="easy")
        engine.advance(60)  # past nation spawn immunity
        engine.attack(target="nation-1", troops=1000)
        after = engine.advance(10)
        # No shared border this early: production retreats the attack.
        assert after["attacks"] == []
        # Engine healthy: both sides alive, game advancing.
        assert after["tick"] > 60
        assert after["nations"][0]["alive"] is True


def test_incoming_attacks_and_troops_are_visible():
    """Dogpile and defense timing need both directions of incoming pressure."""
    with EngineWorker() as engine:
        engine.start(nations=1, difficulty="easy")
        engine.advance(60)  # past nation spawn immunity
        state = engine.query()
        previous_tiles = 0
        for _ in range(15):
            engine.attack(
                target="expand", troops=max(1000, state["human"]["troops"] // 2)
            )
            state = engine.advance(50)
            if state["human"]["tiles"] <= previous_tiles:
                break
            previous_tiles = state["human"]["tiles"]
        engine.attack(
            target="nation-1", troops=max(1000, state["human"]["troops"] // 2)
        )
        after = engine.advance(10)
        # The human's attack shows up as incoming pressure on the nation.
        assert after["nations"][0]["incoming_troops"] > 0
        # Attacks against the human are exposed as their own list.
        assert isinstance(after["incoming_attacks"], list)


def test_attack_rejects_bad_target_and_survives():
    with EngineWorker() as engine:
        engine.start(nations=1, difficulty="easy")
        for bad in ("nation-2", "nation-0", "human-1", "nope", "", 1, None, True):
            try:
                engine.attack(target=bad, troops=1000)  # type: ignore[arg-type]
            except Exception:
                pass
            else:
                raise AssertionError(f"attack accepted bad target {bad!r}")
        assert engine.query()["attacks"] == []
        engine.attack(target="expand", troops=1000)
        assert len(engine.advance(5)["attacks"]) == 1


def test_attack_rejects_bad_troops_and_survives():
    with EngineWorker() as engine:
        engine.start(nations=1, difficulty="easy")
        for bad in (0, -5, "many", None, True):
            try:
                engine.attack(target="expand", troops=bad)  # type: ignore[arg-type]
            except Exception:
                pass
            else:
                raise AssertionError(f"attack accepted bad troops {bad!r}")
        assert engine.query()["attacks"] == []
