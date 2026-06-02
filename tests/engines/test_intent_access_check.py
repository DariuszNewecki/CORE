"""Regression tests for ProtectedNamespaceAccessCheck taint-propagation gaps (#119).

Pure AST-driven tests — no DB fixtures. Each test parses a small source
snippet, runs `ProtectedNamespaceAccessCheck.check_protected_namespace_access`
against it, and asserts on the resulting findings list.

Class previously named `IntentAccessCheck` / method
`check_direct_intent_access` — renamed under #490 (ADR-077 cleanup).

Covers gaps 1-3 from #119:
  - Gap 1: variable-to-variable derivation (multi-hop taint chain)
  - Gap 2: annotated assignment (ast.AnnAssign)
  - Gap 3: augmented assignment (ast.AugAssign)

Plus the gateway-exemption invariant.
"""

from __future__ import annotations

import ast
from pathlib import Path

from mind.logic.engines.ast_gate.checks.protected_namespace_access_check import (
    ProtectedNamespaceAccessCheck,
)


_OUTSIDE_GATEWAY = Path("src/will/some_module.py")
_INSIDE_GATEWAY = Path("src/shared/infrastructure/intent/some_module.py")


def _check(source: str, file_path: Path = _OUTSIDE_GATEWAY) -> list[str]:
    return ProtectedNamespaceAccessCheck.check_protected_namespace_access(
        ast.parse(source), file_path
    )


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


def test_bare_import_yaml_safe_load_is_flagged() -> None:
    """#488: `from yaml import safe_load; safe_load(intent_path)` must flag.

    Pre-#488 the parser called `_full_attr_name(node.func)` which returned
    "safe_load" — not in `_PARSE_CALLS` (which lists "yaml.safe_load"). The
    alias-map resolver now translates the bare name back to its qualified
    form so PARSE_CALLS membership matches.
    """
    source = """
from yaml import safe_load
class C:
    def m(self):
        path = self.intent_root / "rules.yaml"
        safe_load(path.read_text())
"""
    findings = _check(source)
    assert any("safe_load" in f for f in findings)


def test_aliased_yaml_safe_load_resolves_via_alias_map() -> None:
    """#488: `from yaml import safe_load as sl` resolves to qualified form.

    Exercises the alias-map translation directly: ``sl(content)`` becomes
    ``yaml.safe_load(content)`` after resolution, putting it into
    `_PARSE_CALLS` even though the source text never spells out the dotted
    form.
    """
    source = """
from yaml import safe_load as sl
class C:
    def m(self):
        path = self.intent_root / "rules.yaml"
        content = path.read_text()
        sl(content)
"""
    findings = _check(source)
    assert any("yaml.safe_load" in f and "parsing" in f.lower() for f in findings), (
        findings
    )


def test_dotted_yaml_safe_load_still_flagged() -> None:
    """Regression guard: pre-#488 detection path still works."""
    source = """
import yaml
class C:
    def m(self):
        path = self.intent_root / "rules.yaml"
        yaml.safe_load(path.read_text())
"""
    findings = _check(source)
    assert any("safe_load" in f for f in findings)
