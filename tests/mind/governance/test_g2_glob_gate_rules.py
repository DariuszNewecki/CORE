# tests/mind/governance/test_g2_glob_gate_rules.py

"""#842 Unit E: glob_gate blocking-rule fixture pairs.

Depth-verifies the 3 glob_gate blocking rules confirmed to actually work
(architecture.constitution_read_only, architecture.meta_read_only,
governance.constitution.read_only -- all a "path matches a prohibited
.intent/ pattern" shape), plus the missing compliant half of
constitution_read_only (its violating fixture already lives in
test_rule_fires__per_engine_type.py).

file_path is passed directly as the candidate write target, matching the
convention the existing constitution_read_only fixture already
established -- these are immutability guards checked against whatever
path a write operation targets, not a per-source-file content scan (scope
.applies_to: src/**/*.py describes which *callers* this check runs for,
not the shape of file_path itself).

governance.constitution.read_only already had
tests/proof_index/test_claim_09_intent_immutable.py, but that test only
asserts the mapping's shape (engine=glob_gate, patterns_prohibited
contains ".intent", enforcement=blocking) -- it never calls
GlobGateEngine.verify(), so it doesn't satisfy #842's "directly exercise
that symbol" bar. It remains valid as its own regression check; this
file adds the real fixture pair G2 requires.

Not here, per #842's acceptance criteria (claimed enforcement absent or
materially different -> gap + defect, not a fabricated fixture):
- ai.prompt.model_artifact_required, ai.prompt.system_prompt_required --
  #852. Their check_type values (directory_has_required_files,
  files_not_empty) have no dispatch branch in GlobGateEngine.verify();
  both fire on nothing regardless of actual directory/file state.
- autonomy.lanes.boundary_enforcement -- #853. Its scope
  (src/will/agents/**/*.py) and its forbidden `patterns` list
  (src/body/cli/logic/**, etc.) are disjoint directory trees; no file
  the real audit would ever hand this rule can match its own patterns.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from mind.logic.engines.glob_gate import GlobGateEngine


_REPO_ROOT = Path(__file__).parent.parent.parent.parent
_MAPPINGS = _REPO_ROOT / ".intent" / "enforcement" / "mappings"


def _load_rule_params(mapping_rel: str, rule_id: str) -> dict:
    """Read the engine params for rule_id from a mappings YAML."""
    path = _MAPPINGS / mapping_rel
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data["mappings"][rule_id]["params"]


# ---------------------------------------------------------------------------
# architecture.constitution_read_only -- compliant half only; violating half
# already in test_rule_fires__per_engine_type.py.
# ---------------------------------------------------------------------------


async def test_constitution_read_only_clean_for_ordinary_src_file() -> None:
    params = _load_rule_params(
        "architecture/core_safety.yaml", "architecture.constitution_read_only"
    )
    result = await GlobGateEngine().verify(
        Path("src/body/atomic/some_action.py"), params
    )
    assert not result.violations


# ---------------------------------------------------------------------------
# architecture.meta_read_only
# ---------------------------------------------------------------------------


async def test_meta_read_only_fires_on_meta_path() -> None:
    params = _load_rule_params(
        "architecture/core_safety.yaml", "architecture.meta_read_only"
    )
    result = await GlobGateEngine().verify(Path(".intent/META/schema.json"), params)
    assert result.violations


async def test_meta_read_only_clean_for_ordinary_src_file() -> None:
    params = _load_rule_params(
        "architecture/core_safety.yaml", "architecture.meta_read_only"
    )
    result = await GlobGateEngine().verify(
        Path("src/body/atomic/some_action.py"), params
    )
    assert not result.violations


# ---------------------------------------------------------------------------
# governance.constitution.read_only
# ---------------------------------------------------------------------------


async def test_governance_constitution_read_only_fires_on_any_intent_path() -> None:
    params = _load_rule_params(
        "architecture/governance_basics.yaml", "governance.constitution.read_only"
    )
    result = await GlobGateEngine().verify(
        Path(".intent/rules/architecture/core_safety.json"), params
    )
    assert result.violations


async def test_governance_constitution_read_only_clean_for_ordinary_src_file() -> None:
    params = _load_rule_params(
        "architecture/governance_basics.yaml", "governance.constitution.read_only"
    )
    result = await GlobGateEngine().verify(
        Path("src/body/atomic/some_action.py"), params
    )
    assert not result.violations
