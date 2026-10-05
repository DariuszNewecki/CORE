# tests/proof_index/test_claim_09_intent_immutable.py
"""Proof Index claim 9: no code path may write `.intent/` directly.

Standing regression check for docs/proof-index.md claim 9 (#798).
`governance.constitution.read_only` is enforced at runtime by IntentGuard's
tier-1 invariant, declared as a passive_gate (class A) mapping naming
IntentGuard -- the earlier glob_gate mapping could never fire (#936) -- and
the rule definition is `blocking`. The refusal itself is pinned in
tests/body/governance/test_intent_guard__read_only_rules.py.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml


_REPO_ROOT = Path(__file__).resolve().parents[2]
_MAPPING = (
    _REPO_ROOT / ".intent/enforcement/mappings/architecture/governance_basics.yaml"
)
_RULES = _REPO_ROOT / ".intent/rules/architecture/governance_basics.json"


def test_intent_readonly_rule_is_enforced_by_intent_guard() -> None:
    mappings = yaml.safe_load(_MAPPING.read_text(encoding="utf-8"))["mappings"]
    rule = mappings["governance.constitution.read_only"]

    assert rule["engine"] == "passive_gate"
    assert rule["params"]["attestation_class"] == "A"
    assert rule["params"]["enforced_by"] == "body.governance.intent_guard.IntentGuard"


def test_intent_guard_reports_this_rule_id() -> None:
    from body.governance.intent_guard import IntentGuard

    assert IntentGuard._READ_ONLY_RULE_ID == "governance.constitution.read_only"


def test_intent_readonly_rule_is_blocking() -> None:
    rules = json.loads(_RULES.read_text(encoding="utf-8"))["rules"]
    rule = next(r for r in rules if r["id"] == "governance.constitution.read_only")
    assert rule["enforcement"] == "blocking"
