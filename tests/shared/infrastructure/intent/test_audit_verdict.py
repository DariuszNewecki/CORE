# tests/shared/infrastructure/intent/test_audit_verdict.py
"""Tests for shared.infrastructure.intent.audit_verdict — the audit-verdict
policy loader/validator.

ADR-156: adds any_unmapped_mapping_required_rules to the known
degraded_on vocabulary. These tests pin two things directly at the
loader/validator layer (not through ConstitutionalAuditor, which mocks
this module entirely in its own test file):

1. A policy carrying the new precondition validates cleanly — the closed
   _KNOWN_PRECONDITIONS vocabulary now recognizes it.
2. A policy carrying a genuinely unknown precondition still fails
   validation and the loader still converts that into the {"_error": True}
   sentinel — the pre-existing closed-vocabulary rejection is unaffected
   by adding one new known word to it.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from shared.infrastructure.intent.audit_verdict import (
    _validate_policy,
    load_audit_verdict_policy,
)


_VALID_BASE = {
    "fail_severities": ["BLOCK"],
    "ignored_finding_types": ["ENFORCEMENT_FAILURE"],
    "degraded_on": ["any_crashed_rules", "stats_error"],
}


def test_known_preconditions_include_unmapped_mapping_required():
    from shared.infrastructure.intent.audit_verdict import _KNOWN_PRECONDITIONS

    assert "any_unmapped_mapping_required_rules" in _KNOWN_PRECONDITIONS


def test_validate_policy_accepts_unmapped_mapping_required_precondition():
    policy = dict(_VALID_BASE)
    policy["degraded_on"] = [
        "any_crashed_rules",
        "stats_error",
        "any_unmapped_mapping_required_rules",
    ]
    _validate_policy(policy)  # must not raise


def test_validate_policy_still_rejects_unknown_precondition():
    policy = dict(_VALID_BASE)
    policy["degraded_on"] = ["any_crashed_rules", "totally_unrecognized_word"]
    with pytest.raises(ValueError, match="not a known precondition"):
        _validate_policy(policy)


def test_load_audit_verdict_policy_returns_error_sentinel_for_malformed_vocabulary():
    """A degraded_on entry outside _KNOWN_PRECONDITIONS still produces the
    {"_error": True} sentinel end-to-end through the real loader — not a
    silently-accepted policy, and not confused with the new precondition's
    own DEGRADED branch (which only fires on a *valid*, loaded policy).
    """
    malformed = dict(_VALID_BASE)
    malformed["degraded_on"] = ["any_crashed_rules", "not_a_real_precondition"]

    mock_repo = Mock()
    mock_repo.resolve_rel.return_value = "enforcement/config/audit_verdict.yaml"
    mock_repo.load_document.return_value = malformed

    with patch(
        "shared.infrastructure.intent.intent_repository.get_intent_repository",
        return_value=mock_repo,
    ):
        result = load_audit_verdict_policy()

    assert result.get("_error") is True
    assert "not_a_real_precondition" in result.get("reason", "")


def test_load_audit_verdict_policy_accepts_real_policy_with_new_precondition():
    valid = dict(_VALID_BASE)
    valid["degraded_on"] = [
        "any_crashed_rules",
        "stats_error",
        "any_unmapped_mapping_required_rules",
    ]

    mock_repo = Mock()
    mock_repo.resolve_rel.return_value = "enforcement/config/audit_verdict.yaml"
    mock_repo.load_document.return_value = valid

    with patch(
        "shared.infrastructure.intent.intent_repository.get_intent_repository",
        return_value=mock_repo,
    ):
        result = load_audit_verdict_policy()

    assert "_error" not in result
    assert result["degraded_on"] == valid["degraded_on"]
