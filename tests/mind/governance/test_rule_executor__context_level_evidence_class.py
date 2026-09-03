# tests/mind/governance/test_rule_executor__context_level_evidence_class.py

"""ADR-113 D3 boundary at the context-level (verify_context) dispatch path.

execute_rule() stamps every context-level finding with the producing
engine's declared evidence_class (e.g. PROVEN for knowledge_gate). That is
correct for a genuine verdict, but a finding an engine builds *inside*
verify_context() to represent "could not evaluate this source" (unlike the
unsupported-check_type / vocabulary-unavailable guards earlier in
execute_rule(), which return before this loop and keep AuditFinding's
ATTESTED default) has no such early-return path of its own. Promoting it to
PROVEN would render an unevaluated source indistinguishable from a proven
violation — exactly the collapse CORE-Internal-Truthfulness forbids.

Findings self-identify via context["finding_type"] == "ENFORCEMENT_FAILURE";
execute_rule() must honor that marker and leave such findings at the
ATTESTED default rather than stamping the engine's class. #847/#856 extend
the same marker-based carve-out to "ENFORCEMENT_UNAVAILABLE" — a missing
tool or missing evidence source is not a verdict the engine actually
reached either.

Covers the fix both generically (fake engine) and end-to-end through the
real KnowledgeGateEngine.capability_taxonomy_whitelist check_type (#820
Group A) and, for the unavailable-evidence carve-out, the real
RuntimeGateEngine.worker_max_interval_within_observed and
WorkflowGateEngine.quality.type_safety check_types (#847/#856), per the
explicit request to verify through execute_rule() and not only by calling
the private checker.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from mind.governance.audit_context import AuditorContext
from mind.governance.executable_rule import ExecutableRule
from mind.governance.rule_executor import execute_rule
from mind.logic.engines.base import BaseEngine
from mind.logic.engines.knowledge_gate import KnowledgeGateEngine
from mind.logic.engines.runtime_gate import RuntimeGateEngine
from mind.logic.engines.workflow_gate.engine import WorkflowGateEngine
from shared.models import AuditFinding, AuditSeverity, EvidenceClass
from shared.path_resolver import PathResolver


# ID: 2b6e6c9a-2a6f-4a2b-9b7e-2b6e6c9a2a6f
class _FakeContextLevelEngine(BaseEngine):
    """Minimal context-level engine returning a fixed set of findings."""

    engine_id = "fake_context_level"
    evidence_class = EvidenceClass.PROVEN

    def __init__(self, findings: list[AuditFinding]) -> None:
        self._findings = findings

    def verify(self, file_path: Any, params: dict[str, Any]) -> Any:
        raise NotImplementedError("context-level engine; verify() is unused")

    async def verify_context(self, context: Any, params: dict[str, Any]) -> list[AuditFinding]:
        return list(self._findings)


def _make_rule(engine: str = "fake_context_level") -> ExecutableRule:
    return ExecutableRule(
        rule_id="test.context_rule",
        engine=engine,
        params={},
        enforcement="blocking",
        is_context_level=True,
    )


def _patch_engine(monkeypatch: pytest.MonkeyPatch, engine: BaseEngine) -> None:
    monkeypatch.setattr(
        "mind.logic.engines.registry.EngineRegistry.get",
        lambda engine_id: engine,
    )


async def test_genuine_verdict_is_stamped_with_engine_evidence_class(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    finding = AuditFinding(
        check_id="fake.violation",
        severity=AuditSeverity.INFO,
        message="a real violation",
        file_path="src/x.py",
        context={"subject": "x"},
    )
    engine = _FakeContextLevelEngine([finding])
    _patch_engine(monkeypatch, engine)

    results = await execute_rule(_make_rule(), MagicMock(repo_path=Path(".")))

    assert len(results) == 1
    f = results[0]
    assert f.check_id == "test.context_rule"
    assert f.severity == AuditSeverity.BLOCK  # enforcement="blocking"
    assert f.evidence_class == EvidenceClass.PROVEN
    assert f.context == {"subject": "x"}


async def test_enforcement_failure_finding_keeps_attested_not_proven(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    finding = AuditFinding(
        check_id="fake.enforcement_failure",
        severity=AuditSeverity.BLOCK,
        message="ENFORCEMENT_FAILURE: could not evaluate this source",
        file_path="none",
        context={"finding_type": "ENFORCEMENT_FAILURE"},
    )
    engine = _FakeContextLevelEngine([finding])
    _patch_engine(monkeypatch, engine)

    results = await execute_rule(_make_rule(), MagicMock(repo_path=Path(".")))

    assert len(results) == 1
    f = results[0]
    # check_id and severity are still rewritten to the governing rule's —
    # only evidence_class must not be promoted to the engine's PROVEN.
    assert f.check_id == "test.context_rule"
    assert f.severity == AuditSeverity.BLOCK
    assert f.evidence_class == EvidenceClass.ATTESTED, (
        "an ENFORCEMENT_FAILURE finding must never be indistinguishable "
        "from a proven violation"
    )


# ---------------------------------------------------------------------------
# End-to-end through the real engine: #820 Group A
# ---------------------------------------------------------------------------

_TAXONOMY_DOC = {
    "families": {"reasoning": {"capabilities": {"reasoning": {}, "analysis": {}}}}
}


def _make_capability_rule() -> ExecutableRule:
    return ExecutableRule(
        rule_id="capability.taxonomy.roles_require_canonical_capabilities",
        engine="knowledge_gate",
        params={
            "check_type": "capability_taxonomy_whitelist",
            "taxonomy_path": ".intent/taxonomies/capability_taxonomy.yaml",
            "taxonomy_root": "families",
            "database_sources": ["core.cognitive_roles.required_capabilities"],
        },
        enforcement="blocking",
        is_context_level=True,
    )


def _make_kg_context(*, db_session: Any, repo_path: Path) -> MagicMock:
    ctx = MagicMock()
    ctx.repo_path = repo_path
    ctx.intent_repo.load_document = MagicMock(return_value=_TAXONOMY_DOC)
    ctx.db_session = db_session
    return ctx


async def test_real_engine_non_canonical_value_is_proven_violation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from unittest.mock import AsyncMock

    session = AsyncMock()
    result = MagicMock()
    result.fetchall = MagicMock(return_value=[("LocalReasoner", '["yaml_analysis"]')])
    session.execute = AsyncMock(return_value=result)

    engine = KnowledgeGateEngine()
    _patch_engine(monkeypatch, engine)

    results = await execute_rule(
        _make_capability_rule(), _make_kg_context(db_session=session, repo_path=tmp_path)
    )

    assert len(results) == 1
    f = results[0]
    assert f.check_id == "capability.taxonomy.roles_require_canonical_capabilities"
    assert f.severity == AuditSeverity.BLOCK
    assert f.evidence_class == EvidenceClass.PROVEN
    assert f.context["capability"] == "yaml_analysis"
    assert f.context["identity"] == "LocalReasoner"
    assert f.context["table"] == "core.cognitive_roles"


async def test_real_engine_unavailable_db_session_is_unknown_not_proven(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    engine = KnowledgeGateEngine()
    _patch_engine(monkeypatch, engine)

    results = await execute_rule(
        _make_capability_rule(), _make_kg_context(db_session=None, repo_path=tmp_path)
    )

    assert len(results) == 1
    f = results[0]
    assert f.check_id == "capability.taxonomy.roles_require_canonical_capabilities"
    assert f.severity == AuditSeverity.BLOCK  # rule.enforcement is still "blocking"
    assert f.evidence_class == EvidenceClass.ATTESTED, (
        "an unavailable DB source must read as unknown, never as a proven "
        "constitutional violation"
    )
    assert f.context["finding_type"] == "ENFORCEMENT_FAILURE"


# ---------------------------------------------------------------------------
# #847/#856: ENFORCEMENT_UNAVAILABLE gets the same ATTESTED carve-out
# ---------------------------------------------------------------------------


async def test_enforcement_unavailable_finding_keeps_attested_not_proven(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Generic (fake-engine) proof, mirroring
    test_enforcement_failure_finding_keeps_attested_not_proven above."""
    finding = AuditFinding(
        check_id="fake.enforcement_unavailable",
        severity=AuditSeverity.BLOCK,
        message="ENFORCEMENT_UNAVAILABLE: required tool missing",
        file_path="System",
        context={"finding_type": "ENFORCEMENT_UNAVAILABLE"},
    )
    engine = _FakeContextLevelEngine([finding])
    _patch_engine(monkeypatch, engine)

    results = await execute_rule(_make_rule(), MagicMock(repo_path=Path(".")))

    assert len(results) == 1
    f = results[0]
    assert f.check_id == "test.context_rule"
    assert f.severity == AuditSeverity.BLOCK
    assert f.evidence_class == EvidenceClass.ATTESTED, (
        "an ENFORCEMENT_UNAVAILABLE finding must never be indistinguishable "
        "from a proven violation"
    )


async def test_real_workflow_gate_engine_missing_mypy_is_unavailable_not_proven(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """#847 end-to-end: the real quality.type_safety dispatch path
    (WorkflowGateEngine -> QualityGateCheck) with mypy genuinely absent,
    driven through the real execute_rule(), not a fake engine."""
    path_resolver = PathResolver(tmp_path)
    engine = WorkflowGateEngine(path_resolver=path_resolver)
    _patch_engine(monkeypatch, engine)

    rule = ExecutableRule(
        rule_id="quality.type_safety",
        engine="workflow_gate",
        params={
            "check_type": "mypy_check",
            "tools": [{"tool": "mypy", "args": ["--no-error-summary"]}],
        },
        enforcement="blocking",
        is_context_level=True,
    )

    with patch(
        "asyncio.create_subprocess_exec",
        side_effect=FileNotFoundError(2, "No such file or directory", "mypy"),
    ):
        results = await execute_rule(rule, MagicMock(repo_path=tmp_path))

    assert len(results) == 1
    f = results[0]
    assert f.check_id == "quality.type_safety"
    assert f.severity == AuditSeverity.BLOCK  # rule.enforcement is "blocking"
    assert f.evidence_class == EvidenceClass.ATTESTED, (
        "a missing required tool must read as unknown, never as a proven "
        "constitutional violation"
    )
    assert f.context["finding_type"] == "ENFORCEMENT_UNAVAILABLE"


async def test_real_runtime_gate_engine_missing_db_session_is_unavailable_not_proven(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """#856 end-to-end: the real runtime.worker_max_interval_within_observed
    dispatch path (RuntimeGateEngine) with db_session absent, driven
    through the real execute_rule(), not a fake engine."""
    workers_dir = tmp_path / ".intent" / "workers"
    workers_dir.mkdir(parents=True)
    (workers_dir / "alpha.yaml").write_text(
        "metadata:\n  status: active\n"
        "identity:\n  uuid: 11111111-2222-3333-4444-555555555555\n"
        "mandate:\n  schedule:\n    max_interval: 600\n",
        encoding="utf-8",
    )

    engine = RuntimeGateEngine()
    _patch_engine(monkeypatch, engine)

    rule = ExecutableRule(
        rule_id="runtime.worker_max_interval_within_observed",
        engine="runtime_gate",
        params={"check_type": "worker_max_interval_within_observed"},
        enforcement="blocking",
        is_context_level=True,
    )

    ctx = AuditorContext(repo_path=tmp_path)
    assert getattr(ctx, "db_session", None) is None

    results = await execute_rule(rule, ctx)

    assert len(results) == 1
    f = results[0]
    assert f.check_id == "runtime.worker_max_interval_within_observed"
    assert f.severity == AuditSeverity.BLOCK
    assert f.evidence_class == EvidenceClass.ATTESTED, (
        "a missing db_session must read as unknown, never as a proven "
        "constitutional violation"
    )
    assert f.context["finding_type"] == "ENFORCEMENT_UNAVAILABLE"
    assert f.context["reason"] == "db_session_unavailable"


async def test_real_advisory_rule_missing_tool_is_visible_but_info_severity(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Governor ruling 6, real dispatch: quality.security_audit (advisory,
    pip-audit via QualityGateCheck's security_check) with pip-audit absent
    still surfaces ENFORCEMENT_UNAVAILABLE -- visible, per ruling 6 -- but
    at INFO severity (rule.enforcement="advisory" -> _map_enforcement_to_
    severity), never BLOCK. It stays ATTESTED, same carve-out as the
    blocking case; only severity differs, driven by the rule's own tier."""
    path_resolver = PathResolver(tmp_path)
    engine = WorkflowGateEngine(path_resolver=path_resolver)
    _patch_engine(monkeypatch, engine)

    rule = ExecutableRule(
        rule_id="quality.security_audit",
        engine="workflow_gate",
        params={"check_type": "security_check"},
        enforcement="advisory",
        is_context_level=True,
    )

    with patch(
        "asyncio.create_subprocess_exec",
        side_effect=FileNotFoundError(2, "No such file or directory", "pip-audit"),
    ):
        results = await execute_rule(rule, MagicMock(repo_path=tmp_path))

    assert len(results) == 1
    f = results[0]
    assert f.check_id == "quality.security_audit"
    assert f.severity == AuditSeverity.INFO, (
        "an advisory rule's unavailable finding must not carry BLOCK "
        "severity -- it must stay visible without forcing degradation"
    )
    assert f.evidence_class == EvidenceClass.ATTESTED
    assert f.context["finding_type"] == "ENFORCEMENT_UNAVAILABLE"
