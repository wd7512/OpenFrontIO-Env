"""TS evo run: suffix inference, TS validation, streams, template, eval."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from openfrontbench.code_evo import evaluator as evo
from openfrontbench.code_evo import research as _research
from openfrontbench.code_evo import sampler
from openfrontbench.code_evo.evaluator import EvalConfig
from openfrontbench.code_evo.evolve import CandidateError, validate_candidate
from openfrontbench.code_evo.spawns import Spawn, SpawnRegistry
from openfrontbench.paths import REPO_ROOT

TS_POLICY = REPO_ROOT / "policies" / "evolve_me.ts"
TS_TEMPLATE_NAME = "code_evo_research_ts"


def _node_or_skip() -> str:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not on PATH")
    assert node is not None
    return node


def test_policy_filename_for_ts_and_py() -> None:
    assert _research.policy_filename_for(Path("x/evolve_me.ts")) == "evolve_me.ts"
    assert _research.policy_filename_for(Path("x/evolve_me.py")) == "evolve_me.py"


def test_validate_candidate_accepts_ts_baseline() -> None:
    _node_or_skip()
    text = validate_candidate(TS_POLICY)
    assert "class EvolvingPolicy" in text


def test_validate_candidate_rejects_ts_missing_markers(tmp_path: Path) -> None:
    candidate = tmp_path / "policy.ts"
    candidate.write_text(
        "export class EvolvingPolicy { decide(o: any) { return []; } }\n",
        encoding="utf-8",
    )
    with pytest.raises(CandidateError):
        validate_candidate(candidate)


def test_validate_candidate_rejects_ts_banned_global(tmp_path: Path) -> None:
    candidate = tmp_path / "policy.ts"
    candidate.write_text(
        "// EVOLVE-START\nexport class EvolvingPolicy {\n"
        "  decide(o: any) { return Math.random() > 0.5 ? [] : []; }\n"
        "}\n// EVOLVE-END\n",
        encoding="utf-8",
    )
    with pytest.raises(CandidateError):
        validate_candidate(candidate)


def test_validate_candidate_rejects_ts_bad_export(tmp_path: Path) -> None:
    candidate = tmp_path / "policy.ts"
    candidate.write_text(
        "// EVOLVE-START\nexport const x = 1;\n// EVOLVE-END\n",
        encoding="utf-8",
    )
    with pytest.raises(CandidateError):
        validate_candidate(candidate)


def test_validate_candidate_rejects_ts_non_erasable_syntax(
    tmp_path: Path,
) -> None:
    """enum bundles with esbuild but node strip-types rejects it."""
    _node_or_skip()
    source = TS_POLICY.read_text(encoding="utf-8")
    block = source.split("// EVOLVE-START", 1)[1].split("// EVOLVE-END", 1)[0]
    mutant_block = block + "\nenum Extra { A = 1, B = 2 }\n"
    mutant = source.replace(block, mutant_block)
    candidate = tmp_path / "enum_policy.ts"
    candidate.write_text(mutant, encoding="utf-8")
    with pytest.raises(CandidateError):
        validate_candidate(candidate)


def test_ts_order_stream_identical_for_same_file() -> None:
    _node_or_skip()
    spawn = Spawn(id="T", x=50, y=50)
    config = EvalConfig(nations=0, tribes=0, max_ticks=150)
    first = evo.ts_order_stream(TS_POLICY, spawn, "plains", config, "ts-evo-s1")
    second = evo.ts_order_stream(TS_POLICY, spawn, "plains", config, "ts-evo-s1")
    assert first == second
    assert len(first) > 0


def test_ts_order_stream_diverges_on_constant_change(tmp_path: Path) -> None:
    _node_or_skip()
    source = TS_POLICY.read_text(encoding="utf-8")
    mutant_text = source.replace(
        "_EXPAND_SAFE_SMALL_PERCENT = 15", "_EXPAND_SAFE_SMALL_PERCENT = 30"
    )
    assert mutant_text != source
    mutant = tmp_path / "mutant.ts"
    mutant.write_text(mutant_text, encoding="utf-8")
    spawn = Spawn(id="T", x=50, y=50)
    config = EvalConfig(nations=0, tribes=0, max_ticks=150)
    base_stream = evo.ts_order_stream(
        TS_POLICY, spawn, "plains", config, "ts-evo-div", max_ticks=500
    )
    mutant_stream = evo.ts_order_stream(
        mutant, spawn, "plains", config, "ts-evo-div", max_ticks=500
    )
    assert base_stream != mutant_stream


def test_probe_divergence_mixed_language_raises(tmp_path: Path) -> None:
    baseline_py = REPO_ROOT / "src" / "openfrontbench" / "policies" / "evolve_me.py"
    registry = SpawnRegistry(
        map="plains",
        spawns=(Spawn(id="A", x=50, y=50),),
        sha256="x",
        raw={},
    )
    config = EvalConfig(nations=0, tribes=0, max_ticks=150)
    with pytest.raises(ValueError, match="across languages|mixed"):
        evo.probe_divergence(TS_POLICY, baseline_py, registry, config, "mixed-probe")
    with pytest.raises(ValueError, match="across languages|mixed"):
        evo.probe_divergence(baseline_py, TS_POLICY, registry, config, "mixed-probe")


def test_ts_template_renders() -> None:
    template = sampler.load_template(REPO_ROOT / "prompts", name=TS_TEMPLATE_NAME)
    for placeholder in (
        "{best_score}",
        "{best_summary}",
        "{best_source}",
        "{diverse_score}",
        "{diverse_summary}",
        "{diverse_source}",
    ):
        assert placeholder in template
    best = {"mean_score": 123.0, "spawns": [], "source": "fake source"}
    rendered = sampler.render_coding_prompt(template, best, None, "fake source", None)
    assert "123" in rendered
    assert "fake source" in rendered


def test_evaluate_candidate_ts_tiny_plains(tmp_path: Path) -> None:
    _node_or_skip()
    registry = SpawnRegistry(
        map="plains",
        spawns=(Spawn(id="T", x=50, y=50),),
        sha256="abc",
        raw={},
    )
    config = EvalConfig(nations=0, tribes=0, max_ticks=150)
    result = evo.evaluate_candidate(
        TS_POLICY, registry, config, tmp_path / "out", game_id_prefix="ts-eval"
    )
    assert result["episodes"] == 1
    assert result["mean_score"] > 0
    payload = json.loads((tmp_path / "out" / "aggregate.json").read_text())
    assert payload["mean_score"] == result["mean_score"]
