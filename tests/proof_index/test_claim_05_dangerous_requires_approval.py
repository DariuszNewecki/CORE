# tests/proof_index/test_claim_05_dangerous_requires_approval.py
"""Proof Index claim 5: a dangerous/moderate action cannot auto-execute — it needs approval.

Standing regression check for docs/proof-index.md claim 5 (#798). Two invariants:
1. RiskAssessment.requires_approval() is True across the moderate/high band and
   False only for safe — so only a safe-classified proposal auto-executes.
2. An unmapped action_id fails closed to "moderate" (never silently "safe"), so a
   newly-added, unclassified action can never auto-execute.
If either invariant breaks, claim 5 is broken.
"""

from __future__ import annotations

import pytest

from will.autonomy.proposal import RiskAssessment, _resolve_impact


@pytest.mark.parametrize(
    ("overall_risk", "expected"),
    [("safe", False), ("moderate", True), ("high", True)],
)
def test_requires_approval_truth_table(overall_risk: str, expected: bool) -> None:
    assert RiskAssessment(overall_risk=overall_risk).requires_approval() is expected


def test_unmapped_action_fails_closed_to_moderate() -> None:
    # Unknown id → "moderate" (never "safe"); a mapped id passes through unchanged.
    assert _resolve_impact("nonexistent.action.id", {}) == "moderate"
    assert _resolve_impact("known.safe", {"known.safe": "safe"}) == "safe"
