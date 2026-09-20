// Projection + decide edge cases for the TS policy port. The full
// differential proof against the Python champion lives in
// tests/test_ts_policy_parity.py; these pin the projection quirks
// (gold passthrough, tribe filter, nation relabel) without an engine.
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  EvolvingPolicy,
  projectOverview,
  type WorkerSnapshot,
} from "./evolve_me.ts";

function snap(over: Partial<WorkerSnapshot> = {}): WorkerSnapshot {
  return {
    inSpawnPhase: false,
    human: { troops: 60000, gold: "20000", spawnTile: { x: 1, y: 2 } },
    incoming_attacks: [],
    nations: [],
    tribe_list: [],
    units: [],
    ...over,
  };
}

describe("projectOverview", () => {
  it("relabels nations to nation-N in snapshot order", () => {
    const out = projectOverview(
      snap({ nations: [{ id: "zz1" }, { id: "zz2" }] }),
    );
    assert.deepEqual(
      out.nations?.map((n) => n.id),
      ["nation-1", "nation-2"],
    );
  });

  it("keeps only bordering tribes", () => {
    const out = projectOverview(
      snap({
        tribe_list: [
          { id: "tribe-1", borders_human: false },
          { id: "tribe-2", borders_human: true },
        ],
      }),
    );
    assert.deepEqual(
      out.tribes_list?.map((t) => t.id),
      ["tribe-2"],
    );
  });

  it("passes gold through as a string", () => {
    const out = projectOverview(snap());
    assert.equal(out.human?.gold, "20000");
  });
});

describe("decide", () => {
  const policy = new EvolvingPolicy();

  it("passes in spawn phase", () => {
    assert.deepEqual(
      policy.decide({ in_spawn_phase: true, human: { troops: 10 } }),
      [],
    );
  });

  it("never builds a city while gold is a string", () => {
    // Quirk parity with the Python champion: _project carries gold as a
    // bigint string, so _maybeCity is dead. If this ever orders a build,
    // the projection changed and parity is broken.
    const orders = policy.decide(projectOverview(snap()));
    assert.ok(orders.every((o) => o.kind === "attack"));
  });

  it("defends via expand while invaded (retaliation is dead code)", () => {
    // Quirk parity: under attack the policy takes the defend branch
    // (tribes + expands only) and never calls _retaliate; without
    // incoming attacks _retaliate finds no pressure and returns null.
    // Either way no nation attack is ever ordered here.
    const orders = policy.decide(
      projectOverview(
        snap({
          incoming_attacks: [{ attacker: "n", troops: 5, retreating: false }],
          nations: [
            {
              id: "raw",
              troops: 333,
              alive: true,
              borders_human: true,
            },
          ],
        }),
      ),
    );
    assert.deepEqual(orders, [
      {
        kind: "attack",
        target: "expand",
        percent: 10,
        unit: "city",
        x: 0,
        y: 0,
      },
    ]);
  });

  it("never retaliates in peace (empty incoming list)", () => {
    // Parity trap that broke the first e2e run: Python tests truthiness,
    // so empty incoming_attacks means no retaliation even with a weak
    // bordering nation in reach.
    const orders = policy.decide(
      projectOverview(
        snap({
          human: { troops: 901033, gold: "0", spawnTile: { x: 1, y: 2 } },
          incoming_attacks: [],
          nations: [
            { id: "raw", troops: 296133, alive: true, borders_human: true },
          ],
        }),
      ),
    );
    assert.deepEqual(orders, [
      {
        kind: "attack",
        target: "expand",
        percent: 25,
        unit: "city",
        x: 0,
        y: 0,
      },
    ]);
  });

  it("opens 10% on crouch spawns while small", () => {
    const orders = policy.decide(
      projectOverview(
        snap({
          human: { troops: 1000, gold: "0", spawnTile: { x: 1450, y: 1000 } },
        }),
      ),
    );
    assert.equal(orders[0]?.percent, 10);
  });

  it("opens 25% on breakout spawns while small", () => {
    const orders = policy.decide(
      projectOverview(
        snap({
          human: { troops: 1000, gold: "0", spawnTile: { x: 2500, y: 1300 } },
        }),
      ),
    );
    assert.equal(orders[0]?.percent, 25);
  });
});
