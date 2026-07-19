# tests/proof_index/test_claim_01_intent_gateway.py
"""Proof Index claim 1: `.intent/` is reached through a single gateway.

Standing regression check for docs/proof-index.md claim 1 (#798), post-correction.
The IntentRepository facade's non-decomposition is declared in-file via
`CORE_ROLE = "facade"` (ADR-095 D3, which retired the old governed_exclusions
register), and direct `.intent` access outside the gateway is governed by the
`intent_access.json` rules. If the marker or those rules disappear, the
single-gateway guarantee silently weakens.
"""

from __future__ import annotations

import json
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[2]
_FACADE = _REPO_ROOT / "src/shared/infrastructure/intent/intent_repository.py"
_INTENT_ACCESS = _REPO_ROOT / ".intent/rules/architecture/intent_access.json"


def test_intent_repository_declares_facade_role() -> None:
    assert 'CORE_ROLE = "facade"' in _FACADE.read_text(encoding="utf-8")


def test_intent_access_rules_present() -> None:
    ids = {r["id"] for r in json.loads(_INTENT_ACCESS.read_text(encoding="utf-8"))["rules"]}
    assert "architecture.namespace.no_direct_protected_access" in ids
    assert "architecture.intent.gateway_is_shared_infrastructure" in ids
