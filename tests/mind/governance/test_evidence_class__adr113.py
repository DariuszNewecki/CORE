"""ADR-113 — per-finding evidence class (proven / judged / attested).

Proves the honesty mechanism CORE's GRC gap-analysis is sold on:

- every engine declares how it establishes a verdict;
- ``rule_executor`` stamps that declared class onto genuine-verdict findings;
- a crash / unknown verdict degrades to ATTESTED (fail-closed), never a false
  PROVEN (ADR-113 D3);
- the attestation engine SURFACES "needs a human" — it never silently skips
  an un-checkable requirement (ADR-113 D4).

The derivation is exercised through the real ``execute_rule`` path against a
light fake context — the same way the hosted GRC service drives the engine
(call the engine directly; no CLI, no DB).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from mind.governance.executable_rule import ExecutableRule
from mind.governance.rule_executor import execute_rule
from mind.logic.engines.ast_gate.engine import ASTGateEngine
from mind.logic.engines.attestation_gate import AttestationGateEngine
from mind.logic.engines.base import BaseEngine, EngineResult
from mind.logic.engines.llm_gate import LLMGateEngine
from mind.logic.engines.regex_gate import RegexGateEngine
from shared.models import AuditFinding, AuditSeverity, EvidenceClass


# --------------------------------------------------------------------------
# Engine declarations — each engine is the authority on its own class (D2).
# --------------------------------------------------------------------------


def test_deterministic_engines_declare_proven() -> None:
    assert RegexGateEngine.evidence_class is EvidenceClass.PROVEN
    assert ASTGateEngine.evidence_class is EvidenceClass.PROVEN


def test_llm_gate_declares_judged() -> None:
    assert LLMGateEngine.evidence_class is EvidenceClass.JUDGED


def test_attestation_gate_declares_attested() -> None:
    assert AttestationGateEngine.evidence_class is EvidenceClass.ATTESTED


def test_baseengine_default_is_failclosed_attested() -> None:
    # An engine that forgets to declare its class degrades to the weakest,
    # never to a false PROVEN (ADR-113 D3 fail-closed default).
    assert BaseEngine.evidence_class is EvidenceClass.ATTESTED


def test_auditfinding_default_evidence_class_is_attested() -> None:
    f = AuditFinding(check_id="x", severity=AuditSeverity.INFO, message="m")
    assert f.evidence_class is EvidenceClass.ATTESTED


# --------------------------------------------------------------------------
# Test doubles for the derivation path.
# --------------------------------------------------------------------------


class _FakeContext:
    """Minimal stand-in for AuditorContext sufficient for execute_rule."""

    def __init__(self, files: list[Path]) -> None:
        self.repo_path = Path("/repo")
        self._files = files
        self.force_llm = False

    def get_files(self, include: Any, exclude: Any = None) -> list[Path]:
        return self._files


class _ProvenEngine(BaseEngine):
    engine_id = "fake_proven"
    evidence_class = EvidenceClass.PROVEN

    async def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        return EngineResult(False, "x", ["required record absent"], self.engine_id)


class _JudgedEngine(BaseEngine):
    engine_id = "fake_judged"
    evidence_class = EvidenceClass.JUDGED

    async def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        return EngineResult(False, "x", ["policy may not cover remote MFA"], self.engine_id)


class _CrashEngine(BaseEngine):
    # Declares PROVEN, but crashes mid-check: the verdict is genuinely unknown.
    engine_id = "fake_crash"
    evidence_class = EvidenceClass.PROVEN

    async def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        raise RuntimeError("boom")


def _patch_engine(monkeypatch: pytest.MonkeyPatch, engine: BaseEngine) -> None:
    monkeypatch.setattr(
        "mind.logic.engines.registry.EngineRegistry.get",
        lambda engine_id: engine,
    )


# --------------------------------------------------------------------------
# Derivation — execute_rule stamps the producing engine's class (D2/D3).
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_proven_verdict_is_labelled_proven(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_engine(monkeypatch, _ProvenEngine())
    rule = ExecutableRule(
        rule_id="grc.security_policy_exists",
        engine="fake_proven",
        params={},
        enforcement="blocking",
        scope=["**/*.md"],
    )
    findings = await execute_rule(rule, _FakeContext([Path("/repo/security-policy.md")]))
    assert len(findings) == 1
    assert findings[0].evidence_class is EvidenceClass.PROVEN


@pytest.mark.asyncio
async def test_judged_verdict_is_labelled_judged(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_engine(monkeypatch, _JudgedEngine())
    rule = ExecutableRule(
        rule_id="grc.requires_mfa_remote",
        engine="fake_judged",
        params={},
        enforcement="reporting",
        scope=["**/*.md"],
    )
    findings = await execute_rule(rule, _FakeContext([Path("/repo/access-policy.md")]))
    assert len(findings) == 1
    assert findings[0].evidence_class is EvidenceClass.JUDGED


@pytest.mark.asyncio
async def test_crash_degrades_to_attested_never_proven(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A crashed PROVEN engine must NOT yield a 'proven' finding (D3)."""
    _patch_engine(monkeypatch, _CrashEngine())
    rule = ExecutableRule(
        rule_id="grc.security_policy_exists",
        engine="fake_crash",
        params={},
        enforcement="blocking",
        scope=["**/*.md"],
    )
    findings = await execute_rule(rule, _FakeContext([Path("/repo/security-policy.md")]))
    assert len(findings) == 1
    assert findings[0].check_id.endswith("enforcement_failure")
    assert findings[0].evidence_class is EvidenceClass.ATTESTED


@pytest.mark.asyncio
async def test_attestation_is_surfaced_and_labelled_attested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An un-checkable requirement is surfaced as 'needs a human', not skipped."""
    _patch_engine(monkeypatch, AttestationGateEngine())
    rule = ExecutableRule(
        rule_id="grc.controls_appropriate_to_risk",
        engine="attestation_gate",
        params={"prompt": "Confirm security controls are appropriate to the risk."},
        enforcement="reporting",
        scope=["**/*.md"],
        is_context_level=True,
    )
    findings = await execute_rule(rule, _FakeContext([]))
    assert len(findings) == 1
    assert findings[0].evidence_class is EvidenceClass.ATTESTED
    assert "ATTESTATION REQUIRED" in findings[0].message
    assert findings[0].check_id == "grc.controls_appropriate_to_risk"


@pytest.mark.asyncio
async def test_attestation_missing_prompt_is_surfaced_not_silent() -> None:
    """A misconfigured attestation rule surfaces a config finding, never a pass."""
    engine = AttestationGateEngine()
    findings = await engine.verify_context(context=None, params={})
    assert len(findings) == 1
    assert findings[0].context["finding_type"] == "ATTESTATION_MISCONFIGURED"


@pytest.mark.asyncio
async def test_grc_trio_produces_all_three_labels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The slice demo: three requirements, three honesty labels in one report."""
    labels: set[EvidenceClass] = set()

    _patch_engine(monkeypatch, _ProvenEngine())
    proven = await execute_rule(
        ExecutableRule("grc.policy_exists", "fake_proven", {}, "blocking", scope=["**/*.md"]),
        _FakeContext([Path("/repo/policy.md")]),
    )
    labels.update(f.evidence_class for f in proven)

    _patch_engine(monkeypatch, _JudgedEngine())
    judged = await execute_rule(
        ExecutableRule("grc.mfa_remote", "fake_judged", {}, "reporting", scope=["**/*.md"]),
        _FakeContext([Path("/repo/policy.md")]),
    )
    labels.update(f.evidence_class for f in judged)

    _patch_engine(monkeypatch, AttestationGateEngine())
    attested = await execute_rule(
        ExecutableRule(
            "grc.appropriate_to_risk",
            "attestation_gate",
            {"prompt": "Confirm controls are appropriate to the risk."},
            "reporting",
            scope=["**/*.md"],
            is_context_level=True,
        ),
        _FakeContext([]),
    )
    labels.update(f.evidence_class for f in attested)

    assert labels == {
        EvidenceClass.PROVEN,
        EvidenceClass.JUDGED,
        EvidenceClass.ATTESTED,
    }


# --------------------------------------------------------------------------
# Registry sweep — every registered engine must declare its evidence_class
# explicitly (ADR-113 D3 / Consequences: "the linter/test surface should flag
# an undeclared engine so the omission is visible, not silent").
# --------------------------------------------------------------------------


def test_all_registered_engines_declare_evidence_class() -> None:
    """No registered engine may rely silently on the BaseEngine default.

    The fail-closed default (ATTESTED) makes *forgetting* safe, but silent
    omission is invisible.  This test requires an explicit class-level
    ``evidence_class`` attribute in the engine's own ``__dict__`` so the
    omission is a CI failure, not a quiet degradation.
    """
    from mind.logic.engines.registry import EngineRegistry

    EngineRegistry._discover_engines()
    missing = [
        engine_id
        for engine_id, cls in EngineRegistry._engine_classes.items()
        if "evidence_class" not in cls.__dict__
    ]
    assert missing == [], (
        f"Engine(s) missing explicit evidence_class declaration (ADR-113 D3): {missing}"
    )
