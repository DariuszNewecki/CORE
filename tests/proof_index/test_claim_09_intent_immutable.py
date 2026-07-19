# tests/proof_index/test_claim_09_intent_immutable.py
"""Proof Index claim 9: no code path may write `.intent/` directly.

Standing regression check for docs/proof-index.md claim 9 (#798). Thin
"rule-is-mapped-and-would-fire" assertion: `governance.constitution.read_only`
is mapped to `glob_gate` with `.intent/**` prohibited over `src/`, and the rule
definition is `blocking`. If either the mapping or the blocking enforcement is
weakened, `.intent/` immutability silently stops being enforced.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml


_REPO_ROOT = Path(__file__).resolve().parents[2]
_MAPPING = _REPO_ROOT / ".intent/enforcement/mappings/architecture/governance_basics.yaml"
_RULES = _REPO_ROOT / ".intent/rules/architecture/governance_basics.json"


def test_intent_readonly_rule_is_mapped_to_glob_gate() -> None:
    mappings = yaml.safe_load(_MAPPING.read_text(encoding="utf-8"))["mappings"]
    rule = mappings["governance.constitution.read_only"]

    assert rule["engine"] == "glob_gate"
    prohibited = rule["params"]["patterns_prohibited"]
    assert any(".intent" in p for p in prohibited), prohibited
    assert any(p.startswith("src/") for p in rule["scope"]["applies_to"])


def test_intent_readonly_rule_is_blocking() -> None:
    rules = json.loads(_RULES.read_text(encoding="utf-8"))["rules"]
    rule = next(r for r in rules if r["id"] == "governance.constitution.read_only")
    assert rule["enforcement"] == "blocking"
