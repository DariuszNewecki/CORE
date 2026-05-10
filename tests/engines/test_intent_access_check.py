"""Regression tests for IntentAccessCheck taint-propagation gaps (#119).

Pure AST-driven tests — no DB fixtures. Each test parses a small source
snippet, runs `IntentAccessCheck.check_direct_intent_access` against it,
and asserts on the resulting findings list.

Covers gaps 1-3 from #119:
  - Gap 1: variable-to-variable derivation (multi-hop taint chain)
  - Gap 2: annotated assignment (ast.AnnAssign)
  - Gap 3: augmented assignment (ast.AugAssign)

Plus the gateway-exemption invariant.
"""

from __future__ import annotations

import ast
from pathlib import Path

from mind.logic.engines.ast_gate.checks.intent_access_check import (
    IntentAccessCheck,
)


_OUTSIDE_GATEWAY = Path("src/will/some_module.py")
_INSIDE_GATEWAY = Path("src/shared/infrastructure/intent/some_module.py")


def _check(source: str, file_path: Path = _OUTSIDE_GATEWAY) -> list[str]:
    return IntentAccessCheck.check_direct_intent_access(ast.parse(source), file_path)


def test_two_hop_chain_derived_from_intent_root() -> None:
    """Gap 1: variable derived from a tainted variable should still be flagged."""
    source = """
class C:
    def m(self):
        path = self.intent_root
        derived = path / "rules"
        data = derived.read_text()
"""
    findings = _check(source)
    assert len(findings) >= 1, findings
    assert any("read_text" in f for f in findings)


def test_annotated_assignment_propagates_taint() -> None:
    """Gap 2: ast.AnnAssign (`x: T = expr`) should propagate taint."""
    source = """
from pathlib import Path
class C:
    def m(self):
        rules_path: Path = self.intent_root / "rules"
        rules_path.read_text()
"""
    findings = _check(source)
    assert len(findings) >= 1, findings
    assert any("read_text" in f for f in findings)


def test_augmented_assignment_taints_target_via_value() -> None:
    """Gap 3: ast.AugAssign (`p /= ".intent/rules"`) taints the LHS via value."""
    source = """
from pathlib import Path
class C:
    def m(self):
        p = Path("somewhere")
        p /= ".intent/rules"
        p.read_text()
"""
    findings = _check(source)
    assert len(findings) >= 1, findings
    assert any("read_text" in f for f in findings)


def test_clean_module_produces_no_findings() -> None:
    """No .intent reference anywhere — finding count must be zero."""
    source = """
from pathlib import Path

class C:
    def m(self):
        p = Path("somewhere/else")
        p.read_text()
"""
    findings = _check(source)
    assert findings == []


def test_gateway_exemption_returns_empty() -> None:
    """Files inside the sanctioned gateway are exempt regardless of content."""
    source = """
class C:
    def m(self):
        path = self.intent_root
        derived = path / "rules"
        derived.read_text()
"""
    findings = _check(source, file_path=_INSIDE_GATEWAY)
    assert findings == []
