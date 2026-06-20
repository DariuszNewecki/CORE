# tests/shared/models/test_grc_verdict.py
"""Tests for the ADR-118 GRC verdict contract (shared.models.grc_verdict)."""

from __future__ import annotations

import pytest

from shared.models import (
    Applicability,
    EvidenceClass,
    EvidenceItem,
    RequirementStatus,
    RequirementVerdict,
)


def test_enum_string_values_are_lowercase_canonical() -> None:
    # Stored/serialized form is the lowercase value (mirrors EvidenceClass).
    assert str(Applicability.IN_SCOPE) == "in_scope"
    assert str(Applicability.OUT_OF_SCOPE) == "out_of_scope"
    assert str(RequirementStatus.COVERED_UNAUTHORITATIVELY) == "covered_unauthoritatively"
    assert str(RequirementStatus.NOT_COVERED) == "not_covered"
    # str-Enum: usable directly as its string value.
    assert RequirementStatus.SATISFIED == "satisfied"


@pytest.mark.parametrize(
    ("status", "expected_gap"),
    [
        (RequirementStatus.DEFICIENT, True),
        (RequirementStatus.NOT_COVERED, True),
        (RequirementStatus.COVERED_UNAUTHORITATIVELY, True),
        (RequirementStatus.SATISFIED, False),
        (RequirementStatus.NOT_APPLICABLE, False),
        (RequirementStatus.NEEDS_HUMAN, False),
        (RequirementStatus.UNAVAILABLE, False),
    ],
)
def test_is_gap_classifies_the_three_gap_states(
    status: RequirementStatus, expected_gap: bool
) -> None:
    verdict = RequirementVerdict(
        requirement_id="r1",
        applicability=Applicability.IN_SCOPE,
        status=status,
        evidence_class=EvidenceClass.JUDGED,
    )
    assert verdict.is_gap is expected_gap


@pytest.mark.parametrize(
    ("status", "is_verdict"),
    [
        (RequirementStatus.SATISFIED, True),
        (RequirementStatus.DEFICIENT, True),
        (RequirementStatus.NOT_COVERED, True),
        (RequirementStatus.NOT_APPLICABLE, True),
        (RequirementStatus.NEEDS_HUMAN, False),
        (RequirementStatus.UNAVAILABLE, False),
    ],
)
def test_is_verdict_excludes_only_deferred_states(
    status: RequirementStatus, is_verdict: bool
) -> None:
    verdict = RequirementVerdict(
        requirement_id="r1",
        applicability=Applicability.IN_SCOPE,
        status=status,
        evidence_class=EvidenceClass.JUDGED,
    )
    assert verdict.is_verdict is is_verdict


def test_defaults_are_empty_not_shared() -> None:
    a = RequirementVerdict(
        requirement_id="a",
        applicability=Applicability.IN_SCOPE,
        status=RequirementStatus.NOT_COVERED,
        evidence_class=EvidenceClass.JUDGED,
    )
    b = RequirementVerdict(
        requirement_id="b",
        applicability=Applicability.IN_SCOPE,
        status=RequirementStatus.NOT_COVERED,
        evidence_class=EvidenceClass.JUDGED,
    )
    assert a.evidence == []
    assert a.rationale == ""
    a.evidence.append(EvidenceItem(document="d.md", relevance=0.9))
    # default_factory must not share the list between instances
    assert b.evidence == []


def test_evidence_item_authority_optional() -> None:
    # No expected-placement metadata → authority is None (coverage known,
    # placement unknown), per ADR-118 D5 graceful degradation.
    item = EvidenceItem(document="policy.md", relevance=0.8)
    assert item.authority is None
    assert item.cite == ""
    located = EvidenceItem(
        document="policy.md", relevance=0.8, authority=0.95, cite="MFA required for VPN."
    )
    assert located.authority == 0.95
