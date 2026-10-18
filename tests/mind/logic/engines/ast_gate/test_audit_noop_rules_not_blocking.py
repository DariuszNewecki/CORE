# tests/mind/logic/engines/ast_gate/test_audit_noop_rules_not_blocking.py
"""A rule the audit cannot evaluate must not claim to block in the audit.

ast_gate's ``metadata_only_diff`` check_type returns ok without looking at
the file: the rule needs a before/after pair, which only the mutation has
(``file.tag_metadata`` runs ``verify_metadata_only_diff``). A blocking rule
mapped to it passes every audit by construction, so it must be reporting.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from mind.logic.engines.ast_gate.engine import ASTGateEngine


_REPO_ROOT = Path(__file__).resolve().parents[5]
_INTENT = _REPO_ROOT / ".intent"

# check_types ASTGateEngine.verify() answers ok=True without reading the file.
_AUDIT_NOOP_CHECK_TYPES = frozenset({"metadata_only_diff"})


def _enforcement_by_rule_id() -> dict[str, str]:
    levels: dict[str, str] = {}
    for path in (_INTENT / "rules").rglob("*.json"):
        doc = json.loads(path.read_text(encoding="utf-8"))
        for rule in doc.get("rules") or []:
            if isinstance(rule, dict) and "id" in rule:
                levels[rule["id"]] = rule.get("enforcement", "")
    return levels


def _rules_mapped_to(check_types: frozenset[str]) -> set[str]:
    rule_ids: set[str] = set()
    for path in (_INTENT / "enforcement" / "mappings").rglob("*.yaml"):
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for rule_id, mapping in (doc.get("mappings") or {}).items():
            params = (mapping or {}).get("params") or {}
            if mapping.get("engine") == "ast_gate" and (
                params.get("check_type") in check_types
            ):
                rule_ids.add(rule_id)
    return rule_ids


async def test_noop_check_types_really_skip_the_file(tmp_path: Path) -> None:
    """The premise: the engine passes an unreadable file for these check_types."""
    missing = tmp_path / "does_not_exist.py"
    engine = ASTGateEngine(path_resolver=None)  # type: ignore[arg-type]
    for check_type in _AUDIT_NOOP_CHECK_TYPES:
        result = await engine.verify(missing, {"check_type": check_type})
        assert result.ok


def test_rules_mapped_to_audit_noop_checks_are_not_blocking() -> None:
    levels = _enforcement_by_rule_id()
    mapped = _rules_mapped_to(_AUDIT_NOOP_CHECK_TYPES)
    assert mapped, "expected the metadata mutation rules to be mapped"

    blocking = sorted(r for r in mapped if levels.get(r) == "blocking")

    assert blocking == []
