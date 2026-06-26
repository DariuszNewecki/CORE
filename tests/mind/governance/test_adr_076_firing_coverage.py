# tests/mind/governance/test_adr_076_firing_coverage.py

"""ADR-076 D6 — firing-coverage gate for context-level dispatch.

The defect ADR-076 closes is silent inertness: a check_type that is
declared and mapped but never produces a finding under any condition
(`#480`). This test plants a known violation for every ``artifact_gate``
check_type and asserts that ``execute_rule`` — the real audit dispatch
path — returns at least one finding. A check_type that cannot be made
to fire by these tests is inert by definition.

The ADR-066 provocation (``all_rules_mapped`` with a missing
auto_remediation mapping) is included as a fixture case; the live
mutation of the real repo's ``auto_remediation.yaml`` is a governor
action, not test scope.

Workflow_gate and knowledge_gate context-level rules are not covered
file-by-file here because their checks consume system state (test
runner, mypy, knowledge graph) that fixture-planting cannot
realistically reproduce. Their dispatch wiring is asserted by the
extractor truth-table test at the end of this file.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

from mind.governance.audit_context import AuditorContext
from mind.governance.executable_rule import ExecutableRule
from mind.governance.rule_executor import execute_rule
from mind.governance.rule_extractor import extract_executable_rules
from shared.models import AuditSeverity

pytestmark = [pytest.mark.integration]


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _scaffold_repo(tmp_path: Path) -> Path:
    """Build the minimum directory tree artifact_gate's checks look up.

    Repo has ``.intent/`` and ``.specs/`` so the engine's repo-root
    parent-walk resolves. The contents are intentionally bare; each
    test then plants exactly the file it needs to provoke its
    check_type.
    """
    (tmp_path / ".intent").mkdir(exist_ok=True)
    (tmp_path / ".specs").mkdir(exist_ok=True)
    return tmp_path


def _build_context_level_rule(
    rule_id: str, check_type: str, scope_root: Path
) -> ExecutableRule:
    """Build an ExecutableRule wired for context-level dispatch."""
    return ExecutableRule(
        rule_id=rule_id,
        engine="artifact_gate",
        params={"check_type": check_type},
        enforcement="blocking",
        scope=[],
        exclusions=[],
        is_context_level=True,
    )


def _build_per_file_rule(
    rule_id: str, check_type: str, scope: list[str]
) -> ExecutableRule:
    """Build an ExecutableRule wired for per-file dispatch."""
    return ExecutableRule(
        rule_id=rule_id,
        engine="artifact_gate",
        params={"check_type": check_type},
        enforcement="error",
        scope=scope,
        exclusions=[],
        is_context_level=False,
    )


def _seed_enforcement_mapping(
    repo: Path, rule_id: str, check_type: str, scope: list[str]
) -> None:
    """Plant a real enforcement mapping under the fixture's .intent/.

    Written in the production ``mappings:`` shape that
    EnforcementMappingLoader reads, so the loader pointed at the
    fixture root picks it up unchanged.
    """
    mappings_dir = repo / ".intent" / "enforcement" / "mappings"
    mappings_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "mappings": {
            rule_id: {
                "engine": "artifact_gate",
                "params": {"check_type": check_type},
                "scope": {"applies_to": list(scope)},
            }
        }
    }
    (mappings_dir / "test_fixture.yaml").write_text(
        yaml.safe_dump(payload), encoding="utf-8"
    )


def _make_per_file_test_context(
    repo: Path, rule_id: str, check_type: str, scope: list[str]
) -> AuditorContext:
    """Build an AuditorContext that exercises the real D5 derivation.

    ADR-076 D5: AuditorContext.get_files derives its walked set from
    extract_executable_rules(self.policies, self.enforcement_loader).
    For the firing-coverage tests to exercise that path — not bypass it —
    the fixture must seed both inputs:

    1. ``enforcement_loader``: a real mapping YAML planted under the
       fixture's ``.intent/enforcement/mappings/`` so the loader picks
       it up via its normal lazy load.
    2. ``policies``: the IntentRepository singleton is process-pinned
       to the real ``.intent/`` and cannot be redirected to ``tmp_path``,
       so we stub ``ctx.policies`` directly after construction with the
       one rule the test cares about. ``extract_executable_rules`` reads
       this dict as its first argument, so the stub is consumed
       unchanged. ``_per_file_scopes_cache`` is left as None so the
       lazy derivation runs and produces the union under test.

    The result: the firing-coverage tests assert non-emptiness AND
    exercise ``_active_per_file_rule_scopes()`` and its call to
    ``extract_executable_rules`` — a regression in either path would
    surface as an empty union and a test failure.
    """
    _seed_enforcement_mapping(repo, rule_id, check_type, scope)
    ctx = AuditorContext(repo)
    ctx.policies = {
        "test_policy": {
            "rules": [
                {
                    "id": rule_id,
                    "statement": "fixture rule for derivation coverage",
                    "enforcement": "error",
                    "authority": "policy",
                    "phase": "audit",
                }
            ]
        }
    }
    return ctx


def _write_model_yaml(path: Path, contents: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(contents), encoding="utf-8")


# ---------------------------------------------------------------------------
# Per-file artifact_gate check_types (3) — fire through verify(file_path)
# ---------------------------------------------------------------------------


async def test_required_fields_fires_on_missing_field(tmp_path: Path) -> None:
    repo = _scaffold_repo(tmp_path)
    # model.yaml missing 'role' and 'success_criteria'
    _write_model_yaml(
        repo / "var" / "prompts" / "bad_required" / "model.yaml",
        {"id": "x", "version": "1.0"},
    )
    scope = ["var/prompts/**/*.yaml"]
    ctx = _make_per_file_test_context(
        repo, "ai.prompt.artifact.required_fields", "required_fields", scope
    )
    rule = _build_per_file_rule(
        "ai.prompt.artifact.required_fields", "required_fields", scope
    )
    findings = await execute_rule(rule, ctx)
    assert findings, "required_fields produced no findings on a violation fixture"


async def test_no_provider_leak_fires_on_anthropic_preference(tmp_path: Path) -> None:
    repo = _scaffold_repo(tmp_path)
    _write_model_yaml(
        repo / "var" / "prompts" / "leaky" / "model.yaml",
        {
            "id": "x",
            "version": "1.0",
            "role": "Architect",
            "success_criteria": ["ok"],
            "input": {"required": ["q"]},
            "output": {"format": "text"},
            "model": {"preference": "anthropic"},
        },
    )
    scope = ["var/prompts/**/*.yaml"]
    ctx = _make_per_file_test_context(
        repo, "ai.prompt.artifact.no_provider_leak", "no_provider_leak", scope
    )
    rule = _build_per_file_rule(
        "ai.prompt.artifact.no_provider_leak", "no_provider_leak", scope
    )
    findings = await execute_rule(rule, ctx)
    assert findings, "no_provider_leak produced no findings on a violation fixture"


async def test_role_abstraction_fires_on_unknown_role(tmp_path: Path) -> None:
    repo = _scaffold_repo(tmp_path)
    _write_model_yaml(
        repo / "var" / "prompts" / "wrong_role" / "model.yaml",
        {
            "id": "x",
            "version": "1.0",
            "role": "NotARealRole",
            "success_criteria": ["ok"],
            "input": {"required": ["q"]},
            "output": {"format": "text"},
        },
    )
    scope = ["var/prompts/**/*.yaml"]
    ctx = _make_per_file_test_context(
        repo, "ai.prompt.artifact.role_abstraction", "role_abstraction", scope
    )
    rule = _build_per_file_rule(
        "ai.prompt.artifact.role_abstraction", "role_abstraction", scope
    )
    findings = await execute_rule(rule, ctx)
    assert findings, "role_abstraction produced no findings on a violation fixture"


# ---------------------------------------------------------------------------
# Vocabulary artifact_gate check_types (3) — fire through verify_context
# ---------------------------------------------------------------------------


async def test_vocabulary_projection_consistency_fires_when_paper_missing(
    tmp_path: Path,
) -> None:
    """Missing canonical paper makes the projection-vs-paper consistency
    check fail. The check_type dispatches via verify_context."""
    repo = _scaffold_repo(tmp_path)
    # No paper, no projection — the loader reports projection broken.
    ctx = AuditorContext(repo)
    rule = _build_context_level_rule(
        "governance.vocabulary.projection_must_match_canonical",
        "vocabulary_projection_consistency",
        repo,
    )
    findings = await execute_rule(rule, ctx)
    assert findings, "vocabulary_projection_consistency did not fire on missing paper"


async def test_vocabulary_canonical_format_fires_when_paper_missing(
    tmp_path: Path,
) -> None:
    repo = _scaffold_repo(tmp_path)
    ctx = AuditorContext(repo)
    rule = _build_context_level_rule(
        "governance.vocabulary.canonical_format_must_validate",
        "vocabulary_canonical_format",
        repo,
    )
    findings = await execute_rule(rule, ctx)
    assert findings, "vocabulary_canonical_format did not fire on missing paper"


async def test_vocabulary_authoritative_paths_fires_when_paper_missing(
    tmp_path: Path,
) -> None:
    repo = _scaffold_repo(tmp_path)
    ctx = AuditorContext(repo)
    rule = _build_context_level_rule(
        "governance.vocabulary.authoritative_source_must_be_paper",
        "vocabulary_authoritative_paths",
        repo,
    )
    findings = await execute_rule(rule, ctx)
    assert findings, "vocabulary_authoritative_paths did not fire on missing paper"


# ---------------------------------------------------------------------------
# Governance artifact_gate check_types (3) — fire through verify_context
# ---------------------------------------------------------------------------


def _seed_auto_remediation_yaml(repo: Path, mapped_ids: list[str]) -> None:
    """Write auto_remediation.yaml with the given mapping keys."""
    path = repo / ".intent" / "enforcement" / "remediation" / "auto_remediation.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["rules:"]
    for rid in mapped_ids:
        lines.append(f"  {rid}:")
        lines.append("    strategy: DELEGATE")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _seed_rule_document(
    repo: Path, rule_id: str, *, status: str = "active", enforcement: str = "reporting"
) -> None:
    """Write a minimal rule document under .intent/rules/."""
    path = repo / ".intent" / "rules" / "foo.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "metadata": {"status": status},
        "rules": [
            {
                "id": rule_id,
                "statement": "test",
                "enforcement": enforcement,
                "authority": "policy",
                "phase": "audit",
            }
        ],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


async def test_all_rules_mapped_fires_when_mapping_missing(
    tmp_path: Path,
) -> None:
    """ADR-066 invariant: a rule with no auto_remediation mapping must fire.

    This is the firing-coverage proof for the live provocation the
    governor performs against the real repo: the check_type is wired
    so it produces a finding when the invariant is violated.

    Post-#591, ``_check_all_rules_mapped`` reads rules directly from
    ``repo_root/.intent/rules/**/*.json`` (NOT via the
    ``get_intent_repository()`` singleton — see the source docstring), so
    the provocation must live on disk. We plant one active reporting rule
    and leave ``auto_remediation.yaml`` empty so it resolves as unmapped —
    mirroring the disk-only shape of the sibling vocabulary/namespace tests.
    """
    repo = _scaffold_repo(tmp_path)
    _seed_auto_remediation_yaml(repo, mapped_ids=[])  # empty → nothing mapped
    _seed_rule_document(repo, "test.unmapped.rule")  # active + reporting, on disk

    ctx = AuditorContext(repo)
    rule = _build_context_level_rule(
        "governance.remediation.all_rules_mapped",
        "all_rules_mapped",
        repo,
    )
    findings = await execute_rule(rule, ctx)
    assert findings, "all_rules_mapped did not fire when rule was unmapped"
    # ADR-066 D6 provocation: enforcement=blocking → severity must be BLOCK,
    # which is what flips the audit verdict from PASS to FAIL.
    assert any(f.severity is AuditSeverity.BLOCK for f in findings), (
        "all_rules_mapped finding had no BLOCK severity — verdict would not FAIL"
    )


async def test_namespace_has_drainer_fires_when_drainer_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ADR-072: an awaiting_reaudit namespace with no registered drainer fires.

    The check reads the drainer registry via IntentRepository (singleton)
    and queries awaiting_reaudit via the audit context's db_session. We
    mock both so the firing path runs against fixture state, not the
    real repo + database.
    """
    repo = _scaffold_repo(tmp_path)
    # On-disk file present so the check's existence preflight passes; the
    # actual content comes from the mocked IntentRepository below.
    registry_path = (
        repo / ".intent" / "enforcement" / "quarantine" / "drainer_registry.yaml"
    )
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text("namespaces: []\n", encoding="utf-8")

    fake_repo = MagicMock()
    fake_repo.resolve_rel = MagicMock(return_value=Path("dummy"))
    fake_repo.load_document = MagicMock(return_value={"namespaces": []})

    from mind.logic.engines import artifact_gate as agate

    monkeypatch.setattr(agate, "get_intent_repository", lambda: fake_repo)

    ctx = AuditorContext(repo)
    # Inject a mock DB session that returns one row with an unregistered
    # namespace. The check's docstring documents the deferred-when-None
    # contract; we provide one so the violation path runs.
    mock_session = MagicMock()
    mock_result = MagicMock()
    mock_result.fetchall = MagicMock(return_value=[("audit.violation",)])
    mock_session.execute = AsyncMock(return_value=mock_result)
    ctx.db_session = mock_session  # type: ignore[attr-defined]

    rule = _build_context_level_rule(
        "governance.quarantine.namespace_has_drainer",
        "namespace_has_drainer",
        repo,
    )
    findings = await execute_rule(rule, ctx)
    assert findings, "namespace_has_drainer did not fire on unmapped namespace"


async def test_namespace_manifest_completeness_fires_on_unclassified_file(
    tmp_path: Path,
) -> None:
    """ADR-075 D7: a .intent/ or .specs/ file with no manifest entry fires."""
    repo = _scaffold_repo(tmp_path)
    # Plant one unclassified file under .intent/
    (repo / ".intent" / "unclassified.yaml").write_text(
        "hello: world\n", encoding="utf-8"
    )
    # Manifest exists but classifications is empty
    manifest_path = repo / ".intent" / "governance" / "namespace_manifest.yaml"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text("classifications: []\n", encoding="utf-8")

    ctx = AuditorContext(repo)
    rule = _build_context_level_rule(
        "governance.namespace.classification_complete",
        "namespace_manifest_completeness",
        repo,
    )
    findings = await execute_rule(rule, ctx)
    assert findings, "namespace_manifest_completeness did not fire on unclassified file"


# ---------------------------------------------------------------------------
# Wiring proof: every workflow_gate / knowledge_gate rule extracts as
# context-level. This is the firing-coverage proxy for rules whose violation
# paths require live system state (mypy, tests, knowledge graph) that is
# impractical to fixture in a unit test.
# ---------------------------------------------------------------------------


def test_workflow_and_knowledge_gate_rules_are_context_level() -> None:
    """Real-repo extraction: every rule mapped to workflow_gate or
    knowledge_gate must come out of rule_extractor with is_context_level
    = True. This proves D1/D2 wiring for the rules whose firing paths
    require external system state.
    """
    repo = Path("/opt/dev/CORE")
    ctx = AuditorContext(repo)
    rules = extract_executable_rules(ctx.policies, ctx.enforcement_loader)
    misrouted = [
        r.rule_id
        for r in rules
        if r.engine in {"workflow_gate", "knowledge_gate"} and not r.is_context_level
    ]
    assert not misrouted, (
        f"These rules dispatch through context-level engines but were "
        f"extracted as per-file: {misrouted}"
    )


def test_active_per_file_rule_scopes_derives_from_policies_and_loader(
    tmp_path: Path,
) -> None:
    """ADR-076 D5 derivation regression gate.

    ``AuditorContext._active_per_file_rule_scopes()`` must return the
    sorted union of include-patterns from rules where
    ``is_context_level == False``. A regression in any of the moving
    parts surfaces here:
    - ``extract_executable_rules`` failing to hydrate rules from
      (policies, loader);
    - the ``is_context_level == False`` filter inverting or being
      dropped (context-level scopes would leak into the union and
      widen the walked set silently);
    - empty / malformed scope patterns slipping through.
    """
    repo = _scaffold_repo(tmp_path)
    # Two per-file rules with distinct scopes — both must surface.
    _seed_enforcement_mapping(
        repo,
        "test.per_file.alpha",
        "required_fields",
        ["var/prompts/**/*.yaml"],
    )
    mappings_dir = repo / ".intent" / "enforcement" / "mappings"
    (mappings_dir / "test_fixture_beta.yaml").write_text(
        yaml.safe_dump(
            {
                "mappings": {
                    "test.per_file.beta": {
                        "engine": "artifact_gate",
                        "params": {"check_type": "role_abstraction"},
                        "scope": {"applies_to": ["src/**/*.py"]},
                    },
                    # One context-level rule — its scope MUST NOT enter
                    # the union (it would silently widen the walked set
                    # back toward scan-all and re-open the #480 class).
                    "test.context_level.gamma": {
                        "engine": "artifact_gate",
                        "params": {"check_type": "all_rules_mapped"},
                        "scope": {"applies_to": [".intent/**/*.yaml"]},
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    ctx = AuditorContext(repo)
    ctx.policies = {
        "test_policy": {
            "rules": [
                {
                    "id": "test.per_file.alpha",
                    "statement": "alpha",
                    "enforcement": "error",
                    "authority": "policy",
                    "phase": "audit",
                },
                {
                    "id": "test.per_file.beta",
                    "statement": "beta",
                    "enforcement": "error",
                    "authority": "policy",
                    "phase": "audit",
                },
                {
                    "id": "test.context_level.gamma",
                    "statement": "gamma",
                    "enforcement": "blocking",
                    "authority": "policy",
                    "phase": "audit",
                },
            ]
        }
    }

    union = ctx._active_per_file_rule_scopes()

    # The two per-file scopes appear; the context-level scope does NOT.
    assert "var/prompts/**/*.yaml" in union
    assert "src/**/*.py" in union
    assert ".intent/**/*.yaml" not in union, (
        "Context-level rule scope leaked into the per-file union — the "
        "is_context_level filter is inverted or missing."
    )
    # The result is sorted, deduplicated, and otherwise nothing extra.
    assert union == sorted(set(union))


def test_artifact_gate_mixed_mode_extraction() -> None:
    """artifact_gate's six repo-level check_types extract context-level;
    its three PromptModel check_types extract per-file.
    """
    repo = Path("/opt/dev/CORE")
    ctx = AuditorContext(repo)
    rules = extract_executable_rules(ctx.policies, ctx.enforcement_loader)
    artifact_rules = [r for r in rules if r.engine == "artifact_gate"]

    repo_level_check_types = {
        "vocabulary_projection_consistency",
        "vocabulary_canonical_format",
        "vocabulary_authoritative_paths",
        "all_rules_mapped",
        "namespace_has_drainer",
        "namespace_manifest_completeness",
    }
    per_file_check_types = {
        "required_fields",
        "no_provider_leak",
        "role_abstraction",
    }

    for r in artifact_rules:
        ct = r.params.get("check_type")
        if ct in repo_level_check_types:
            assert r.is_context_level, (
                f"{r.rule_id} ({ct}) should be context-level but is per-file"
            )
        elif ct in per_file_check_types:
            assert not r.is_context_level, (
                f"{r.rule_id} ({ct}) should be per-file but is context-level"
            )
