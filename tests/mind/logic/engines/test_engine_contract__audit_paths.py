"""ADR-176 D3 baseline (#1339 PR B): today's behaviour, per audit path, for
the two cases outside the version 1 guarantee.

1. No LLM configured. ``EngineRegistry.get`` substitutes ``LLMGateStubEngine``
   for an engine that takes ``llm_client``; the stand-in is built on every
   call and not kept.
2. An engine that cannot be built (its constructor raises).

Audit paths: the registry itself, the single-rule path (``execute_rule``), the
full audit (``run_dynamic_rules``), gap analysis
(``DocumentCorpusAnalysisService.run``) and the record path
(``record_contract.evaluate``).

These tests pin what CORE does on main; they do not say it is right. ADR-176
leaves it unchanged, and making it one behaviour is separate work. Later #1339
PRs must keep them green without editing them.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import mind.governance.constitutional_auditor_dynamic as cad
from body.services.grc.gap_analysis_service import DocumentCorpusAnalysisService
from mind.governance.executable_rule import ExecutableRule
from mind.governance.rule_executor import execute_rule
from mind.logic import record_contract
from mind.logic.engines.base import BaseEngine, EngineResult
from mind.logic.engines.llm_gate_stub import LLMGateStubEngine
from mind.logic.engines.registry import EngineRegistry
from shared.models import AuditSeverity, EvidenceClass, RequirementStatus


_LLM_ENGINES = ["llm_gate", "grc_judge"]


class _RuntimeErrorEngine(BaseEngine):
    """Cannot be built: its constructor raises RuntimeError."""

    engine_id = "contract_runtime_error_gate"
    supports_records = True

    def __init__(self) -> None:
        raise RuntimeError("cannot build: runtime error")

    async def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        raise AssertionError("never built")


class _ValueErrorEngine(BaseEngine):
    """Cannot be built: its constructor raises ValueError."""

    engine_id = "contract_value_error_gate"
    supports_records = True

    def __init__(self) -> None:
        raise ValueError("cannot build: value error")

    async def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        raise AssertionError("never built")


_UNBUILDABLE = {
    _RuntimeErrorEngine.engine_id: _RuntimeErrorEngine,
    _ValueErrorEngine.engine_id: _ValueErrorEngine,
}
_RT = _RuntimeErrorEngine.engine_id
_VE = _ValueErrorEngine.engine_id


def _rule(engine_id: str) -> ExecutableRule:
    return ExecutableRule(
        rule_id=f"contract.{engine_id}",
        engine=engine_id,
        params={},
        enforcement="blocking",
    )


async def _full_audit(rule: ExecutableRule) -> tuple[list[Any], set[str], set[str]]:
    executed: set[str] = set()
    crashed: set[str] = set()
    with (
        patch.object(cad, "extract_executable_rules", return_value=[rule]),
        patch.object(cad, "_check_per_file_scope_coverage", return_value=[]),
    ):
        findings = await cad.run_dynamic_rules(
            MagicMock(), executed_rule_ids=executed, crashed_rule_ids=crashed
        )
    return findings, executed, crashed


async def _gap_analysis(rule: ExecutableRule, corpus: Path) -> list[Any]:
    """Gap analysis with no LLM client; run() re-initializes the registry,
    so the unbuildable test engines are added after its initialize."""
    original = EngineRegistry.initialize

    def _initialize(*args: Any, **kwargs: Any) -> None:
        original(*args, **kwargs)
        EngineRegistry._engine_classes.update(_UNBUILDABLE)

    (corpus / "doc.md").write_text("a document\n")
    with patch(
        "body.services.grc.gap_analysis_service.EngineRegistry.initialize",
        side_effect=_initialize,
    ):
        return await DocumentCorpusAnalysisService().run(corpus, catalog=[rule])


def _record_rule(engine_id: str) -> record_contract.RecordRule:
    return record_contract.RecordRule(rule_id=f"record.{engine_id}", engine=engine_id)


# --- 1. No LLM configured ----------------------------------------------------


@pytest.mark.parametrize("engine_id", _LLM_ENGINES)
def test_no_llm__registry_builds_a_new_stand_in_per_call_and_keeps_none(
    fresh_engine_registry: type[EngineRegistry], engine_id: str
) -> None:
    first = fresh_engine_registry.get(engine_id)
    second = fresh_engine_registry.get(engine_id)
    assert type(first) is LLMGateStubEngine
    assert type(second) is LLMGateStubEngine
    assert first is not second
    assert engine_id not in fresh_engine_registry._instances


@pytest.mark.parametrize("engine_id", _LLM_ENGINES)
async def test_no_llm__single_rule_path_gives_one_stub_warning(
    fresh_engine_registry: type[EngineRegistry], engine_id: str
) -> None:
    rule = _rule(engine_id)
    findings = await execute_rule(rule, MagicMock())
    assert len(findings) == 1
    finding = findings[0]
    assert finding.check_id == rule.rule_id
    assert finding.severity == AuditSeverity.HIGH
    assert finding.context["stub"] is True
    assert finding.context["reason"] == "no_llm_client"


async def test_no_llm__full_audit_gives_llm_gate_the_stub_warning(
    fresh_engine_registry: type[EngineRegistry],
) -> None:
    # #1454 fixed: the rule was counted as executed with no finding (a
    # silent pass); it now gets the same #307 warning as on the single-rule
    # path.
    rule = _rule("llm_gate")
    findings, executed, crashed = await _full_audit(rule)
    assert [(f.check_id, f.severity) for f in findings] == [
        (rule.rule_id, AuditSeverity.HIGH)
    ]
    assert findings[0].context["stub"] is True
    assert executed == {rule.rule_id}
    assert crashed == set()


async def test_no_llm__full_audit_gives_grc_judge_the_stub_warning(
    fresh_engine_registry: type[EngineRegistry],
) -> None:
    rule = _rule("grc_judge")
    findings, executed, crashed = await _full_audit(rule)
    assert [(f.check_id, f.severity) for f in findings] == [
        (rule.rule_id, AuditSeverity.HIGH)
    ]
    assert findings[0].context["stub"] is True
    assert executed == {rule.rule_id}
    assert crashed == set()


async def test_no_llm__gap_analysis_gives_grc_judge_unavailable(
    fresh_engine_registry: type[EngineRegistry], tmp_path: Path
) -> None:
    (verdict,) = await _gap_analysis(_rule("grc_judge"), tmp_path)
    assert verdict.status == RequirementStatus.UNAVAILABLE
    assert verdict.evidence_class == EvidenceClass.JUDGED


async def test_no_llm__gap_analysis_gives_llm_gate_deficient(
    fresh_engine_registry: type[EngineRegistry], tmp_path: Path
) -> None:
    # Today the stub warning from execute_rule is classified as a gap.
    (verdict,) = await _gap_analysis(_rule("llm_gate"), tmp_path)
    assert verdict.status == RequirementStatus.DEFICIENT
    assert verdict.evidence_class == EvidenceClass.JUDGED


@pytest.mark.parametrize("engine_id", _LLM_ENGINES)
async def test_no_llm__record_path_gives_engine_missing(
    fresh_engine_registry: type[EngineRegistry], engine_id: str
) -> None:
    # LLM engines do not judge records; no client is ever injected there.
    verdict = await record_contract.evaluate({}, [_record_rule(engine_id)])
    (part,) = verdict.parts
    assert part.result == "fail"
    assert part.evidence_class == EvidenceClass.ATTESTED
    (finding,) = part.findings
    assert finding.details == {"finding_type": "engine_missing"}
    assert "does not judge records" in finding.message


# --- 2. An engine that cannot be built ---------------------------------------


@pytest.mark.parametrize(
    ("engine_id", "error"), [(_RT, RuntimeError), (_VE, ValueError)]
)
def test_unbuildable__registry_raises_the_constructor_error_and_keeps_nothing(
    fresh_engine_registry: type[EngineRegistry],
    engine_id: str,
    error: type[Exception],
) -> None:
    fresh_engine_registry._engine_classes.update(_UNBUILDABLE)
    with pytest.raises(error, match="cannot build"):
        fresh_engine_registry.get(engine_id)
    assert engine_id not in fresh_engine_registry._instances


async def test_unbuildable__single_rule_path_lets_a_runtime_error_through(
    fresh_engine_registry: type[EngineRegistry],
) -> None:
    fresh_engine_registry._engine_classes.update(_UNBUILDABLE)
    with pytest.raises(RuntimeError, match="cannot build"):
        await execute_rule(_rule(_RT), MagicMock())


async def test_unbuildable__single_rule_path_turns_a_value_error_into_engine_missing(
    fresh_engine_registry: type[EngineRegistry],
) -> None:
    fresh_engine_registry._engine_classes.update(_UNBUILDABLE)
    rule = _rule(_VE)
    findings = await execute_rule(rule, MagicMock())
    assert [(f.check_id, f.severity) for f in findings] == [
        (f"{rule.rule_id}.engine_missing", AuditSeverity.BLOCK)
    ]


async def test_unbuildable__full_audit_gives_an_enforcement_failure(
    fresh_engine_registry: type[EngineRegistry],
) -> None:
    fresh_engine_registry._engine_classes.update(_UNBUILDABLE)
    rule = _rule(_RT)
    findings, executed, crashed = await _full_audit(rule)
    assert [(f.check_id, f.severity) for f in findings] == [
        (rule.rule_id, AuditSeverity.BLOCK)
    ]
    assert findings[0].context["finding_type"] == "ENFORCEMENT_FAILURE"
    assert executed == {rule.rule_id}
    assert crashed == {rule.rule_id}


async def test_unbuildable__full_audit_turns_a_value_error_into_engine_missing(
    fresh_engine_registry: type[EngineRegistry],
) -> None:
    # #1458: changed on purpose. A ValueError from get() was an
    # ENFORCEMENT_FAILURE crash here; it is now engine-missing, as on the
    # single-rule path.
    fresh_engine_registry._engine_classes.update(_UNBUILDABLE)
    rule = _rule(_VE)
    findings, executed, crashed = await _full_audit(rule)
    assert [(f.check_id, f.severity) for f in findings] == [
        (f"{rule.rule_id}.engine_missing", AuditSeverity.BLOCK)
    ]
    assert executed == {rule.rule_id}
    assert crashed == set()


async def test_unbuildable__gap_analysis_lets_a_runtime_error_through(
    fresh_engine_registry: type[EngineRegistry], tmp_path: Path
) -> None:
    with pytest.raises(RuntimeError, match="cannot build"):
        await _gap_analysis(_rule(_RT), tmp_path)


async def test_unbuildable__gap_analysis_turns_a_value_error_into_unavailable(
    fresh_engine_registry: type[EngineRegistry], tmp_path: Path
) -> None:
    # #1458: changed on purpose. A ValueError from get() ended the run; it is
    # now the engine-missing finding, reported as UNAVAILABLE.
    rule = _rule(_VE)
    (verdict,) = await _gap_analysis(rule, tmp_path)
    assert verdict.status == RequirementStatus.UNAVAILABLE
    assert verdict.evidence_class == EvidenceClass.ATTESTED
    assert verdict.rationale.startswith(f"{rule.rule_id}.engine_missing: ")


async def test_unbuildable__record_path_lets_a_runtime_error_through(
    fresh_engine_registry: type[EngineRegistry],
) -> None:
    fresh_engine_registry._engine_classes.update(_UNBUILDABLE)
    with pytest.raises(RuntimeError, match="cannot build"):
        await record_contract.evaluate({}, [_record_rule(_RT)])


async def test_unbuildable__record_path_turns_a_value_error_into_engine_missing(
    fresh_engine_registry: type[EngineRegistry],
) -> None:
    fresh_engine_registry._engine_classes.update(_UNBUILDABLE)
    verdict = await record_contract.evaluate({}, [_record_rule(_VE)])
    (part,) = verdict.parts
    assert part.result == "fail"
    (finding,) = part.findings
    assert finding.details == {"finding_type": "engine_missing"}
    assert "cannot build" in finding.message


# --- 3. An engine id the registry does not hold (#1458, ADR-176 D3) ----------

_UNKNOWN = "contract_no_such_gate"


async def test_unknown_engine__single_rule_path_gives_engine_missing(
    fresh_engine_registry: type[EngineRegistry],
) -> None:
    rule = _rule(_UNKNOWN)
    findings = await execute_rule(rule, MagicMock())
    assert [(f.check_id, f.severity) for f in findings] == [
        (f"{rule.rule_id}.engine_missing", AuditSeverity.BLOCK)
    ]


async def test_unknown_engine__full_audit_gives_engine_missing(
    fresh_engine_registry: type[EngineRegistry],
) -> None:
    rule = _rule(_UNKNOWN)
    findings, executed, crashed = await _full_audit(rule)
    assert [(f.check_id, f.severity) for f in findings] == [
        (f"{rule.rule_id}.engine_missing", AuditSeverity.BLOCK)
    ]
    assert executed == {rule.rule_id}
    assert crashed == set()


async def test_unknown_engine__gap_analysis_gives_engine_missing_as_unavailable(
    fresh_engine_registry: type[EngineRegistry], tmp_path: Path
) -> None:
    rule = _rule(_UNKNOWN)
    (verdict,) = await _gap_analysis(rule, tmp_path)
    assert verdict.status == RequirementStatus.UNAVAILABLE
    assert verdict.evidence_class == EvidenceClass.ATTESTED
    assert verdict.rationale.startswith(f"{rule.rule_id}.engine_missing: ")


async def test_unknown_engine__record_path_gives_engine_missing(
    fresh_engine_registry: type[EngineRegistry],
) -> None:
    verdict = await record_contract.evaluate({}, [_record_rule(_UNKNOWN)])
    (part,) = verdict.parts
    assert part.result == "fail"
    (finding,) = part.findings
    assert finding.details == {"finding_type": "engine_missing"}
