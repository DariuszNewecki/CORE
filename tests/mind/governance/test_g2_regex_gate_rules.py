# tests/mind/governance/test_g2_regex_gate_rules.py

"""#842 Unit D: regex_gate blocking-rule fixture pairs.

Depth-verifies the 13 regex_gate blocking rules that had zero prior test
coverage referencing them by rule_id, plus the missing compliant half of
architecture.path_access.no_hardcoded_runtime_dirs (its violating fixture
already lives in test_rule_fires__per_engine_type.py).

Each pair follows that file's established pattern: load real params from
the live `.intent/enforcement/mappings/` YAML, instantiate the real
RegexGateEngine, run it against a real violating and a real compliant
snippet, assert both directions. Every example pair here was verified
against the live engine before being written into this file, not
authored from the pattern text alone.

governance.intent_artifact_encoding.ascii_only WAS not here -- its mapping
used a schema (`pattern` + `match_means`) RegexGateEngine.verify() never
read, so the rule fired on nothing regardless of content (#851). Now fixed:
the mapping uses `forbidden_patterns` (the real schema), and the 248 live
.intent/ files it newly caught (958 em dashes, 859 box-drawing dividers,
and 11 other non-ASCII symbols across comments and content) were cleaned
via a purely mechanical 1:1 character substitution -- verified via a fresh
regex sweep of the whole corpus (0 remaining non-ASCII bytes outside
.intent/META/) and a full IntentRepository.initialize() (145 documents,
343 policies, 257 rules -- unchanged counts pre/post cleanup) before this
fixture pair was added.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
import yaml

from mind.logic.engines.regex_gate import RegexGateEngine


_REPO_ROOT = Path(__file__).parent.parent.parent.parent
_MAPPINGS = _REPO_ROOT / ".intent" / "enforcement" / "mappings"


def _load_rule_params(mapping_rel: str, rule_id: str) -> dict:
    """Read the engine params for rule_id from a mappings YAML."""
    path = _MAPPINGS / mapping_rel
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data["mappings"][rule_id]["params"]


@pytest.fixture
def tmp_py(tmp_path: Path) -> Path:
    """Temp Python file under var/tmp/ (CLAUDE.md prohibits /tmp/)."""
    dest = _REPO_ROOT / "var" / "tmp" / f"g2_regex_{uuid.uuid4().hex}.py"
    dest.parent.mkdir(parents=True, exist_ok=True)
    yield dest
    dest.unlink(missing_ok=True)


@pytest.fixture
def tmp_intent_yaml(tmp_path: Path) -> Path:
    """Temp .yaml file under var/tmp/, matching this rule's own .intent/**/*.yaml
    applies_to shape (content is what the engine reads, not the real path)."""
    dest = _REPO_ROOT / "var" / "tmp" / f"g2_regex_intent_{uuid.uuid4().hex}.yaml"
    dest.parent.mkdir(parents=True, exist_ok=True)
    yield dest
    dest.unlink(missing_ok=True)


@pytest.fixture
def engine() -> RegexGateEngine:
    return RegexGateEngine()


# ---------------------------------------------------------------------------
# architecture.path_access.no_hardcoded_runtime_dirs -- compliant half only;
# violating half already in test_rule_fires__per_engine_type.py.
# ---------------------------------------------------------------------------


async def test_no_hardcoded_runtime_dirs_clean_via_path_resolver(
    tmp_py: Path, engine: RegexGateEngine
) -> None:
    params = _load_rule_params(
        "architecture/path_access.yaml",
        "architecture.path_access.no_hardcoded_runtime_dirs",
    )
    tmp_py.write_text('path = path_resolver.reports_dir / "x.json"\n', encoding="utf-8")
    result = await engine.verify(tmp_py, params)
    assert not result.violations, (
        f"PathResolver-routed path should not false-positive; got {result.violations}"
    )


# ---------------------------------------------------------------------------
# ai.cognitive_role.no_hardcoded_string
# ---------------------------------------------------------------------------


async def test_cognitive_role_hardcoded_string_fires(
    tmp_py: Path, engine: RegexGateEngine
) -> None:
    params = _load_rule_params(
        "ai/cognitive_role_governance.yaml", "ai.cognitive_role.no_hardcoded_string"
    )
    tmp_py.write_text('x = aget_client_for_role("Coder")\n', encoding="utf-8")
    result = await engine.verify(tmp_py, params)
    assert result.violations


async def test_cognitive_role_manifest_derived_role_is_clean(
    tmp_py: Path, engine: RegexGateEngine
) -> None:
    params = _load_rule_params(
        "ai/cognitive_role_governance.yaml", "ai.cognitive_role.no_hardcoded_string"
    )
    tmp_py.write_text(
        "x = aget_client_for_role(model.manifest.role)\n", encoding="utf-8"
    )
    result = await engine.verify(tmp_py, params)
    assert not result.violations


# ---------------------------------------------------------------------------
# architecture.blackboard.worker_only_inserts
# ---------------------------------------------------------------------------


async def test_worker_only_inserts_fires_on_raw_insert(
    tmp_py: Path, engine: RegexGateEngine
) -> None:
    params = _load_rule_params(
        "architecture/blackboard.yaml", "architecture.blackboard.worker_only_inserts"
    )
    tmp_py.write_text(
        'await session.execute(text("INSERT INTO core.blackboard_entries (id) VALUES (1)"))\n',
        encoding="utf-8",
    )
    result = await engine.verify(tmp_py, params)
    assert result.violations


async def test_worker_only_inserts_clean_via_post_finding(
    tmp_py: Path, engine: RegexGateEngine
) -> None:
    params = _load_rule_params(
        "architecture/blackboard.yaml", "architecture.blackboard.worker_only_inserts"
    )
    tmp_py.write_text('await self.post_finding("x", {})\n', encoding="utf-8")
    result = await engine.verify(tmp_py, params)
    assert not result.violations


# ---------------------------------------------------------------------------
# architecture.flows.atomic_action_must_not_compose
# ---------------------------------------------------------------------------


async def test_atomic_action_must_not_compose_fires(
    tmp_py: Path, engine: RegexGateEngine
) -> None:
    params = _load_rule_params(
        "architecture/flows.yaml", "architecture.flows.atomic_action_must_not_compose"
    )
    tmp_py.write_text(
        "result = await action_executor.execute(action)\n", encoding="utf-8"
    )
    result = await engine.verify(tmp_py, params)
    assert result.violations


async def test_atomic_action_must_not_compose_clean_when_no_composition(
    tmp_py: Path, engine: RegexGateEngine
) -> None:
    params = _load_rule_params(
        "architecture/flows.yaml", "architecture.flows.atomic_action_must_not_compose"
    )
    tmp_py.write_text("return ActionResult(ok=True, data={})\n", encoding="utf-8")
    result = await engine.verify(tmp_py, params)
    assert not result.violations


# ---------------------------------------------------------------------------
# architecture.flows.flow_declared_in_intent
# ---------------------------------------------------------------------------


async def test_flow_declared_in_intent_fires_on_direct_registration(
    tmp_py: Path, engine: RegexGateEngine
) -> None:
    params = _load_rule_params(
        "architecture/flows.yaml", "architecture.flows.flow_declared_in_intent"
    )
    tmp_py.write_text("register_flow(my_flow)\n", encoding="utf-8")
    result = await engine.verify(tmp_py, params)
    assert result.violations


async def test_flow_declared_in_intent_clean_via_registry_load(
    tmp_py: Path, engine: RegexGateEngine
) -> None:
    params = _load_rule_params(
        "architecture/flows.yaml", "architecture.flows.flow_declared_in_intent"
    )
    tmp_py.write_text('flow = FlowRegistry.load("my_flow")\n', encoding="utf-8")
    result = await engine.verify(tmp_py, params)
    assert not result.violations


# ---------------------------------------------------------------------------
# architecture.flows.flow_must_not_create_proposals
# ---------------------------------------------------------------------------


async def test_flow_must_not_create_proposals_fires(
    tmp_py: Path, engine: RegexGateEngine
) -> None:
    params = _load_rule_params(
        "architecture/flows.yaml", "architecture.flows.flow_must_not_create_proposals"
    )
    tmp_py.write_text('p = Proposal(goal="x")\n', encoding="utf-8")
    result = await engine.verify(tmp_py, params)
    assert result.violations


async def test_flow_must_not_create_proposals_clean_when_no_proposal(
    tmp_py: Path, engine: RegexGateEngine
) -> None:
    params = _load_rule_params(
        "architecture/flows.yaml", "architecture.flows.flow_must_not_create_proposals"
    )
    tmp_py.write_text("return FlowResult(ok=True)\n", encoding="utf-8")
    result = await engine.verify(tmp_py, params)
    assert not result.violations


# ---------------------------------------------------------------------------
# architecture.flows.flow_must_not_post_to_blackboard
# ---------------------------------------------------------------------------


async def test_flow_must_not_post_to_blackboard_fires(
    tmp_py: Path, engine: RegexGateEngine
) -> None:
    params = _load_rule_params(
        "architecture/flows.yaml", "architecture.flows.flow_must_not_post_to_blackboard"
    )
    tmp_py.write_text('await self.post_finding("x", {})\n', encoding="utf-8")
    result = await engine.verify(tmp_py, params)
    assert result.violations


async def test_flow_must_not_post_to_blackboard_clean_when_no_posting(
    tmp_py: Path, engine: RegexGateEngine
) -> None:
    params = _load_rule_params(
        "architecture/flows.yaml", "architecture.flows.flow_must_not_post_to_blackboard"
    )
    tmp_py.write_text("return FlowResult(ok=True)\n", encoding="utf-8")
    result = await engine.verify(tmp_py, params)
    assert not result.violations


# ---------------------------------------------------------------------------
# atomic_actions.impact_level_must_be_governed
# ---------------------------------------------------------------------------


async def test_impact_level_must_be_governed_fires_on_inline_assignment(
    tmp_py: Path, engine: RegexGateEngine
) -> None:
    params = _load_rule_params(
        "architecture/atomic_actions.yaml",
        "atomic_actions.impact_level_must_be_governed",
    )
    tmp_py.write_text('impact_level = "high"\n', encoding="utf-8")
    result = await engine.verify(tmp_py, params)
    assert result.violations


async def test_impact_level_must_be_governed_clean_when_not_assigned_inline(
    tmp_py: Path, engine: RegexGateEngine
) -> None:
    params = _load_rule_params(
        "architecture/atomic_actions.yaml",
        "atomic_actions.impact_level_must_be_governed",
    )
    tmp_py.write_text("return ActionResult(ok=True, data={})\n", encoding="utf-8")
    result = await engine.verify(tmp_py, params)
    assert not result.violations


# ---------------------------------------------------------------------------
# capability.taxonomy.no_model_specific_names
# ---------------------------------------------------------------------------


async def test_no_model_specific_names_fires_on_model_name(
    tmp_py: Path, engine: RegexGateEngine
) -> None:
    params = _load_rule_params(
        "ai/capability_taxonomy_governance.yaml",
        "capability.taxonomy.no_model_specific_names",
    )
    tmp_py.write_text("capabilities:\n  - claude\n", encoding="utf-8")
    result = await engine.verify(tmp_py, params)
    assert result.violations


async def test_no_model_specific_names_clean_for_canonical_capability(
    tmp_py: Path, engine: RegexGateEngine
) -> None:
    params = _load_rule_params(
        "ai/capability_taxonomy_governance.yaml",
        "capability.taxonomy.no_model_specific_names",
    )
    tmp_py.write_text("capabilities:\n  - embedding\n", encoding="utf-8")
    result = await engine.verify(tmp_py, params)
    assert not result.violations


# ---------------------------------------------------------------------------
# data.security.no_raw_secrets
# ---------------------------------------------------------------------------


async def test_no_raw_secrets_fires_on_hardcoded_password(
    tmp_py: Path, engine: RegexGateEngine
) -> None:
    params = _load_rule_params("data/governance.yaml", "data.security.no_raw_secrets")
    tmp_py.write_text('PASSWORD = "supersecretvalue123"\n', encoding="utf-8")
    result = await engine.verify(tmp_py, params)
    assert result.violations


async def test_no_raw_secrets_clean_when_read_from_env(
    tmp_py: Path, engine: RegexGateEngine
) -> None:
    params = _load_rule_params("data/governance.yaml", "data.security.no_raw_secrets")
    tmp_py.write_text('PASSWORD = os.environ["DB_PASSWORD"]\n', encoding="utf-8")
    result = await engine.verify(tmp_py, params)
    assert not result.violations


# ---------------------------------------------------------------------------
# governance.fs_operations.no_direct_yaml_import
# ---------------------------------------------------------------------------


async def test_no_direct_yaml_import_fires_on_direct_read(
    tmp_py: Path, engine: RegexGateEngine
) -> None:
    params = _load_rule_params(
        "governance/fs_operations.yaml",
        "governance.fs_operations.no_direct_yaml_import",
    )
    tmp_py.write_text(
        'data = yaml.safe_load(open("filesystem_operations.yaml"))\n', encoding="utf-8"
    )
    result = await engine.verify(tmp_py, params)
    assert result.violations


async def test_no_direct_yaml_import_clean_via_sanctioned_loader(
    tmp_py: Path, engine: RegexGateEngine
) -> None:
    params = _load_rule_params(
        "governance/fs_operations.yaml",
        "governance.fs_operations.no_direct_yaml_import",
    )
    tmp_py.write_text("data = load_filesystem_operations()\n", encoding="utf-8")
    result = await engine.verify(tmp_py, params)
    assert not result.violations


# ---------------------------------------------------------------------------
# governance.vocabulary.no_direct_json_import
# ---------------------------------------------------------------------------


async def test_no_direct_json_import_fires_on_direct_read(
    tmp_py: Path, engine: RegexGateEngine
) -> None:
    params = _load_rule_params(
        "governance/vocabulary_canonical_store.yaml",
        "governance.vocabulary.no_direct_json_import",
    )
    tmp_py.write_text(
        'data = json.loads(open("vocabulary.json").read())\n', encoding="utf-8"
    )
    result = await engine.verify(tmp_py, params)
    assert result.violations


async def test_no_direct_json_import_clean_via_sanctioned_loader(
    tmp_py: Path, engine: RegexGateEngine
) -> None:
    params = _load_rule_params(
        "governance/vocabulary_canonical_store.yaml",
        "governance.vocabulary.no_direct_json_import",
    )
    tmp_py.write_text("data = load_vocabulary_projection()\n", encoding="utf-8")
    result = await engine.verify(tmp_py, params)
    assert not result.violations


# ---------------------------------------------------------------------------
# planning.file_path_validation
# ---------------------------------------------------------------------------


async def test_file_path_validation_fires_on_spaced_slash(
    tmp_py: Path, engine: RegexGateEngine
) -> None:
    params = _load_rule_params("will/planning.yaml", "planning.file_path_validation")
    tmp_py.write_text('p = "src / foo.py"\n', encoding="utf-8")
    result = await engine.verify(tmp_py, params)
    assert result.violations


async def test_file_path_validation_clean_for_normal_path(
    tmp_py: Path, engine: RegexGateEngine
) -> None:
    params = _load_rule_params("will/planning.yaml", "planning.file_path_validation")
    tmp_py.write_text('p = "src/foo.py"\n', encoding="utf-8")
    result = await engine.verify(tmp_py, params)
    assert not result.violations


# ---------------------------------------------------------------------------
# governance.intent_artifact_encoding.ascii_only (#851, now closed)
# ---------------------------------------------------------------------------


async def test_ascii_only_fires_on_em_dash(
    tmp_intent_yaml: Path, engine: RegexGateEngine
) -> None:
    params = _load_rule_params(
        "governance/intent_artifact_encoding.yaml",
        "governance.intent_artifact_encoding.ascii_only",
    )
    tmp_intent_yaml.write_text(
        "description: word " + chr(0x2014) + " word\n", encoding="utf-8"
    )  # em dash (U+2014), the rule's own textbook violation
    result = await engine.verify(tmp_intent_yaml, params)
    assert result.violations


async def test_ascii_only_clean_for_plain_ascii(
    tmp_intent_yaml: Path, engine: RegexGateEngine
) -> None:
    params = _load_rule_params(
        "governance/intent_artifact_encoding.yaml",
        "governance.intent_artifact_encoding.ascii_only",
    )
    tmp_intent_yaml.write_text("description: word -- word\n", encoding="utf-8")
    result = await engine.verify(tmp_intent_yaml, params)
    assert not result.violations
