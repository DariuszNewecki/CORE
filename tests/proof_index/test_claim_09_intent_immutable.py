# tests/proof_index/test_claim_09_intent_immutable.py
"""Proof Index claim 9: no code path may write `.intent/` directly.

Standing regression check for docs/proof-index.md claim 9 (#798).
`governance.constitution.read_only` is enforced at runtime by IntentGuard's
tier-1 invariant; no audit rule checks it (the passive rule was retired in
phase 5b). The refusal itself is pinned in
tests/body/governance/test_intent_guard__read_only_rules.py.
"""

from __future__ import annotations


def test_intent_guard_reports_this_rule_id() -> None:
    from body.governance.intent_guard import IntentGuard

    assert IntentGuard._READ_ONLY_RULE_ID == "governance.constitution.read_only"
