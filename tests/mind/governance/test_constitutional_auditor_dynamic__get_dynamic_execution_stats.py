# tests/mind/governance/test_constitutional_auditor_dynamic__get_dynamic_execution_stats.py
"""Mapping-required accounting in the dynamic auditor (#820 Group B prereq).

The unmapped-rule set and the effective-coverage denominator must both use
the canonical rule_requires_enforcement_mapping predicate, so that demoting a
rule to advisory and removing its mapping does not manufacture a phantom
unmapped-rule finding or depress coverage. Before this change the audit
counted advisory rules while DispatchParityCheck excluded them — two
independent interpretations of "mapping required".

The four governor-mandated proofs:
  1. advisory rule without mapping is NOT reported as unmapped;
  2. reporting rule without mapping IS reported as unmapped;
  3. blocking rule without mapping IS reported as unmapped;
  4. advisory markers do not reduce effective enforcement coverage.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import mind.governance.constitutional_auditor_dynamic as cad
from mind.governance.constitutional_auditor_dynamic import (
    _find_unmapped_rule_ids,
    _mapping_required_rule_ids,
    get_dynamic_execution_stats,
    run_dynamic_rules,
)
from mind.governance.executable_rule import ExecutableRule
from mind.logic.engines.base import EvidenceClass
from shared.models import AuditFinding, AuditSeverity


def _policies(*rules: tuple[str, str]) -> dict[str, Any]:
    """Build a policies dict from (rule_id, enforcement) pairs."""
    return {
        "test_policy": {
            "rules": [{"id": rid, "enforcement": enf} for rid, enf in rules]
        }
    }


# --- Proof 1: advisory without mapping is not unmapped -----------------------


def test_advisory_rule_without_mapping_is_not_unmapped() -> None:
    policies = _policies(("b.rule", "blocking"), ("a.marker", "advisory"))
    # a.marker has no mapping, so it is not in the executable set.
    unmapped = _find_unmapped_rule_ids(policies, executable_rule_ids={"b.rule"})
    assert unmapped == []


# --- Proofs 2 & 3: reporting / blocking without mapping ARE unmapped ---------


def test_reporting_rule_without_mapping_is_unmapped() -> None:
    policies = _policies(("b.rule", "blocking"), ("r.orphan", "reporting"))
    unmapped = _find_unmapped_rule_ids(policies, executable_rule_ids={"b.rule"})
    assert unmapped == ["r.orphan"]


def test_blocking_rule_without_mapping_is_unmapped() -> None:
    policies = _policies(("r.rule", "reporting"), ("b.orphan", "blocking"))
    unmapped = _find_unmapped_rule_ids(policies, executable_rule_ids={"r.rule"})
    assert unmapped == ["b.orphan"]


def test_mapping_required_excludes_only_advisory() -> None:
    policies = _policies(
        ("b.rule", "blocking"),
        ("r.rule", "reporting"),
        ("a.marker", "advisory"),
    )
    assert _mapping_required_rule_ids(policies) == {"b.rule", "r.rule"}


# --- Proof 4: advisory markers do not reduce effective coverage --------------


def _rule(rule_id: str) -> ExecutableRule:
    return ExecutableRule(
        rule_id=rule_id,
        engine="ast_gate",
        params={"check_type": "docstrings_present"},
        enforcement="blocking",
    )


def _context(policies: dict[str, Any]) -> Any:
    ctx = MagicMock()
    ctx.policies = policies
    ctx.enforcement_loader = MagicMock()
    return ctx


def test_advisory_marker_does_not_reduce_effective_coverage(
    monkeypatch: object,
) -> None:
    """Adding an unmapped advisory marker leaves effective coverage unchanged.

    Two blocking rules are mapped and cleanly executed. Introducing a third
    rule that is advisory-with-no-mapping must not drag coverage below 100% —
    it is not an enforcement hole. Under the pre-fix denominator (all declared
    rules) coverage would have been 2/3 = 67%.
    """
    executable = [_rule("b.one"), _rule("b.two")]
    monkeypatch.setattr(cad, "extract_executable_rules", lambda *_a, **_k: executable)

    executed = {"b.one", "b.two"}

    without_marker = get_dynamic_execution_stats(
        _context(_policies(("b.one", "blocking"), ("b.two", "blocking"))),
        executed_rule_ids=set(executed),
    )
    with_marker = get_dynamic_execution_stats(
        _context(
            _policies(
                ("b.one", "blocking"),
                ("b.two", "blocking"),
                ("a.marker", "advisory"),
            )
        ),
        executed_rule_ids=set(executed),
    )

    assert without_marker["effective_coverage_percent"] == 100
    assert with_marker["effective_coverage_percent"] == 100
    assert with_marker["unmapped_rules"] == 0
    # The advisory marker is still counted in the honest total-declared stat.
    assert with_marker["total_declared_rules"] == 3
    assert with_marker["mapping_required_rules"] == 2


def test_reporting_hole_reduces_coverage_and_is_reported(
    monkeypatch: object,
) -> None:
    """The mirror of proof 4: a non-advisory hole DOES reduce coverage.

    One blocking rule mapped and executed, one reporting rule with no mapping.
    Coverage is 1/2 = 50% and the reporting rule is reported unmapped — the
    predicate discriminates by tier, it does not blanket-exempt everything.
    """
    executable = [_rule("b.one")]
    monkeypatch.setattr(cad, "extract_executable_rules", lambda *_a, **_k: executable)

    stats = get_dynamic_execution_stats(
        _context(_policies(("b.one", "blocking"), ("r.orphan", "reporting"))),
        executed_rule_ids={"b.one"},
    )

    assert stats["effective_coverage_percent"] == 50
    assert stats["unmapped_rules"] == 1
    assert stats["unmapped_rule_ids"] == ["r.orphan"]
    assert stats["mapping_required_rules"] == 2


# --- #847/#856: unavailable_rule_ids, split by enforcement tier -------------


def _rule_tier(rule_id: str, enforcement: str) -> ExecutableRule:
    return ExecutableRule(
        rule_id=rule_id,
        engine="ast_gate",
        params={"check_type": "docstrings_present"},
        enforcement=enforcement,
    )


def test_blocking_unavailable_rule_is_counted_in_blocking_unavailable_stats(
    monkeypatch: object,
) -> None:
    """A blocking rule's unavailable_rule_ids entry lands in
    blocking_unavailable_rule_ids -- the field _determine_verdict's DEGRADED
    precondition consumes."""
    executable = [_rule_tier("b.one", "blocking")]
    monkeypatch.setattr(cad, "extract_executable_rules", lambda *_a, **_k: executable)

    stats = get_dynamic_execution_stats(
        _context(_policies(("b.one", "blocking"))),
        executed_rule_ids={"b.one"},
        crashed_rule_ids=set(),
        unavailable_rule_ids={"b.one"},
    )

    assert stats["unavailable_rules"] == 1
    assert stats["unavailable_rule_ids"] == ["b.one"]
    assert stats["blocking_unavailable_rules"] == 1
    assert stats["blocking_unavailable_rule_ids"] == ["b.one"]


def test_advisory_unavailable_rule_is_excluded_from_blocking_unavailable_stats(
    monkeypatch: object,
) -> None:
    """Governor ruling 6: an advisory rule's unavailable dependency remains
    visible in unavailable_rule_ids (the general count) but is EXCLUDED from
    blocking_unavailable_rule_ids -- it must not force DEGRADED."""
    executable = [_rule_tier("a.one", "advisory")]
    monkeypatch.setattr(cad, "extract_executable_rules", lambda *_a, **_k: executable)

    stats = get_dynamic_execution_stats(
        _context(_policies(("a.one", "advisory"))),
        executed_rule_ids={"a.one"},
        crashed_rule_ids=set(),
        unavailable_rule_ids={"a.one"},
    )

    assert stats["unavailable_rules"] == 1
    assert stats["unavailable_rule_ids"] == ["a.one"]
    assert stats["blocking_unavailable_rules"] == 0
    assert stats["blocking_unavailable_rule_ids"] == []


def test_no_unavailable_rules_yields_zero_stats(monkeypatch: object) -> None:
    executable = [_rule_tier("b.one", "blocking")]
    monkeypatch.setattr(cad, "extract_executable_rules", lambda *_a, **_k: executable)

    stats = get_dynamic_execution_stats(
        _context(_policies(("b.one", "blocking"))),
        executed_rule_ids={"b.one"},
    )

    assert stats["unavailable_rules"] == 0
    assert stats["blocking_unavailable_rules"] == 0


# --- #847/#856: run_dynamic_rules tracks unavailable separately from crashed,
# through the real execute_rule dispatch path (not a helper-unit test) -------


async def test_run_dynamic_rules_tracks_unavailable_separately_from_crashed() -> None:
    """Governor rulings 1/2: an unavailable enforcement dependency is
    distinct from an unexpected engine crash. In the same audit run, one
    rule reports ENFORCEMENT_UNAVAILABLE (via the real execute_rule ->
    engine.verify_context dispatch, engine not mocked away at that layer)
    and a second rule crashes. The two must land in disjoint tracking sets,
    never conflated."""

    class _UnavailableEngine:
        engine_id = "runtime_gate"

        async def verify_context(self, *_a: object, **_k: object) -> list[Any]:
            return [
                AuditFinding(
                    check_id="runtime.worker_max_interval_within_observed",
                    severity=AuditSeverity.BLOCK,
                    message="db_session unavailable",
                    file_path="none",
                    context={
                        "finding_type": "ENFORCEMENT_UNAVAILABLE",
                        "reason": "db_session_unavailable",
                    },
                )
            ]

    class _CrashingEngine:
        engine_id = "ast_gate"

        async def verify_context(self, *_a: object, **_k: object) -> list[Any]:
            raise RuntimeError("boom")

    unavailable_rule = ExecutableRule(
        rule_id="runtime.worker_max_interval_within_observed",
        engine="runtime_gate",
        params={"check_type": "worker_max_interval_within_observed"},
        enforcement="blocking",
        is_context_level=True,
    )
    crashing_rule = ExecutableRule(
        rule_id="some.crashing.rule",
        engine="ast_gate",
        params={"check_type": "whatever"},
        enforcement="blocking",
        is_context_level=True,
    )

    engines = {
        "runtime_gate": _UnavailableEngine(),
        "ast_gate": _CrashingEngine(),
    }

    executed_rule_ids: set[str] = set()
    crashed_rule_ids: set[str] = set()
    unavailable_rule_ids: set[str] = set()

    with (
        patch(
            "mind.governance.constitutional_auditor_dynamic.extract_executable_rules",
            return_value=[unavailable_rule, crashing_rule],
        ),
        patch(
            "mind.logic.engines.registry.EngineRegistry.get",
            side_effect=lambda engine_id: engines[engine_id],
        ),
    ):
        findings = await run_dynamic_rules(
            _context(_policies()),
            executed_rule_ids=executed_rule_ids,
            crashed_rule_ids=crashed_rule_ids,
            unavailable_rule_ids=unavailable_rule_ids,
        )

    assert unavailable_rule_ids == {"runtime.worker_max_interval_within_observed"}
    assert crashed_rule_ids == {"some.crashing.rule"}
    # Genuinely disjoint -- neither set contains the other's rule.
    assert unavailable_rule_ids.isdisjoint(crashed_rule_ids)

    unavailable_findings = [
        f
        for f in findings
        if isinstance(f.context, dict)
        and f.context.get("finding_type") == "ENFORCEMENT_UNAVAILABLE"
    ]
    assert len(unavailable_findings) == 1
    # ADR-113 D3 carve-out (extended by #847/#856): unavailable findings are
    # never stamped with a real evidence_class -- they keep AuditFinding's
    # ATTESTED default, same as ENFORCEMENT_FAILURE.
    assert unavailable_findings[0].evidence_class == EvidenceClass.ATTESTED
