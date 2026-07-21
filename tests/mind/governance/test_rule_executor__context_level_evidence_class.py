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
ATTESTED default rather than stamping the engine's class.

Covers the fix both generically (fake engine) and end-to-end through the
real KnowledgeGateEngine.capability_taxonomy_whitelist check_type (#820
Group A), per the explicit request to verify through execute_rule() and
not only by calling the private checker.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from mind.governance.executable_rule import ExecutableRule
from mind.governance.rule_executor import execute_rule
from mind.logic.engines.base import BaseEngine
from mind.logic.engines.knowledge_gate import KnowledgeGateEngine
from shared.models import AuditFinding, AuditSeverity, EvidenceClass


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
