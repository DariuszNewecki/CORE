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
- autonomy.lanes.boundary_enforcement -- #853. Its scope
  (src/will/agents/**/*.py) and its forbidden `patterns` list
  (src/body/cli/logic/**, etc.) are disjoint directory trees; no file
  the real audit would ever hand this rule can match its own patterns.
  Still a gap: the fix is a rule-design decision (governor), not a reflex
  patch, unlike the two rules below.

ai.prompt.model_artifact_required and ai.prompt.system_prompt_required were
originally gap rows too (#852: GlobGateEngine.verify() had no dispatch
branch for either check_type, so both fired on nothing). #852 is now closed
-- GlobGateEngine gained real `directory_has_required_files` and
`files_not_empty` dispatch branches. Both use their own substring-based
path matching rather than the pre-existing `_match()` helper: real dispatch
(rule_executor.py's per-file audit loop) always hands an absolute
filesystem path, but `_match()`'s prefix branch only ever does a leading
`str.startswith`, which can never match an absolute path against a
repo-relative pattern prefix like "var/prompts" -- confirmed by writing
these fixtures with a real tmp_path (necessarily absolute) rather than the
relative Path(...) literals the constitution_read_only-style fixtures above
use (those go through a different, write-interception call path that
passes a relative candidate path, per this file's own note above). Both
rules' fixture pairs below use tmp_path-relative var/prompts/ layouts
matching each rule's own applies_to scope, not an arbitrary path.
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


# ---------------------------------------------------------------------------
# ai.prompt.model_artifact_required (#852, now closed)
# ---------------------------------------------------------------------------


async def test_model_artifact_required_fires_on_missing_manifest_files(
    tmp_path: Path,
) -> None:
    params = _load_rule_params(
        "ai/prompt_governance.yaml", "ai.prompt.model_artifact_required"
    )
    prompt_dir = tmp_path / "var" / "prompts" / "incomplete_prompt"
    prompt_dir.mkdir(parents=True)
    (prompt_dir / "system.txt").write_text("You are a helpful assistant.")
    # model.yaml and user.txt are missing.

    result = await GlobGateEngine().verify(prompt_dir / "system.txt", params)

    assert result.violations
    assert "model.yaml" in result.violations[0]
    assert "user.txt" in result.violations[0]


async def test_model_artifact_required_clean_when_all_three_present(
    tmp_path: Path,
) -> None:
    params = _load_rule_params(
        "ai/prompt_governance.yaml", "ai.prompt.model_artifact_required"
    )
    prompt_dir = tmp_path / "var" / "prompts" / "complete_prompt"
    prompt_dir.mkdir(parents=True)
    (prompt_dir / "model.yaml").write_text("provider: anthropic\n")
    (prompt_dir / "system.txt").write_text("You are a helpful assistant.")
    (prompt_dir / "user.txt").write_text("{{task}}")

    result = await GlobGateEngine().verify(prompt_dir / "system.txt", params)

    assert not result.violations


async def test_model_artifact_required_skips_loose_file_directly_under_root(
    tmp_path: Path,
) -> None:
    """A file sitting directly in var/prompts/ (not inside a subdirectory,
    e.g. a loose .md note) is not a governed module -- proves the "not
    inside a subdirectory" skip path is a real no-op, not an accidental
    always-pass."""
    params = _load_rule_params(
        "ai/prompt_governance.yaml", "ai.prompt.model_artifact_required"
    )
    prompts_root = tmp_path / "var" / "prompts"
    prompts_root.mkdir(parents=True)
    loose_file = prompts_root / "README.md"
    loose_file.write_text("notes")

    result = await GlobGateEngine().verify(loose_file, params)

    assert not result.violations


# ---------------------------------------------------------------------------
# ai.prompt.system_prompt_required (#852, now closed)
# ---------------------------------------------------------------------------


async def test_system_prompt_required_fires_on_empty_system_txt(
    tmp_path: Path,
) -> None:
    params = _load_rule_params(
        "ai/prompt_governance.yaml", "ai.prompt.system_prompt_required"
    )
    prompt_dir = tmp_path / "var" / "prompts" / "empty_prompt"
    prompt_dir.mkdir(parents=True)
    system_txt = prompt_dir / "system.txt"
    system_txt.write_text("   \n  \n")  # whitespace-only

    result = await GlobGateEngine().verify(system_txt, params)

    assert result.violations


async def test_system_prompt_required_clean_for_populated_system_txt(
    tmp_path: Path,
) -> None:
    params = _load_rule_params(
        "ai/prompt_governance.yaml", "ai.prompt.system_prompt_required"
    )
    prompt_dir = tmp_path / "var" / "prompts" / "populated_prompt"
    prompt_dir.mkdir(parents=True)
    system_txt = prompt_dir / "system.txt"
    system_txt.write_text("You are a helpful assistant.")

    result = await GlobGateEngine().verify(system_txt, params)

    assert not result.violations


async def test_system_prompt_required_ignores_empty_non_system_file(
    tmp_path: Path,
) -> None:
    """An empty model.yaml in the same directory must NOT trip this rule --
    proves the fixed _match() suffix handling actually scopes the pattern to
    system.txt files, not to every file under var/prompts/** (the pre-fix
    _match() ignored the "/system.txt" suffix entirely and would have
    matched any file here)."""
    params = _load_rule_params(
        "ai/prompt_governance.yaml", "ai.prompt.system_prompt_required"
    )
    prompt_dir = tmp_path / "var" / "prompts" / "mixed_prompt"
    prompt_dir.mkdir(parents=True)
    (prompt_dir / "system.txt").write_text("You are a helpful assistant.")
    empty_model_yaml = prompt_dir / "model.yaml"
    empty_model_yaml.write_text("")

    result = await GlobGateEngine().verify(empty_model_yaml, params)

    assert not result.violations
