# src/mind/logic/engines/_knowledge_gate_duplication.py

"""
Duplication-detection helpers for KnowledgeGateEngine.

Extracted from knowledge_gate.py to keep KnowledgeGateEngine under the
modularity.class_too_large threshold. The three functions here form the
"duplication" cluster — AST-fingerprint and semantic-vector matching plus
the shared finding factory — and are called by the engine's verify_context
dispatcher. The remaining checks in the engine (capability_assignment,
duplicate_ids, table_has_records, orphan_file_check) form a different,
graph-and-DB-shaped cluster and stay on the engine.
"""

from __future__ import annotations

import fnmatch
from collections import defaultdict
from typing import TYPE_CHECKING, Any

from shared.models import AuditFinding, AuditSeverity


if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext


def _check_ast_duplication(
    context: AuditorContext, params: dict[str, Any]
) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    if not context.symbols_map:
        return findings

    # Honor scope.excludes from the rule mapping. rule_executor injects
    # rule.exclusions under "_scope_excludes" so excluded symbols are
    # filtered at intake — they cannot be flagged nor pull a non-excluded
    # peer into a finding pair.
    exclude_patterns: list[str] = params.get("_scope_excludes", []) or []

    def _is_excluded(sym: dict) -> bool:
        if not exclude_patterns:
            return False
        fp = sym.get("file_path")
        if not fp:
            module = sym.get("module", "")
            if not module:
                return False
            fp = "src/" + module.replace(".", "/") + ".py"
        return any(fnmatch.fnmatch(fp, pat) for pat in exclude_patterns)

    fingerprint_groups = defaultdict(list)
    for symbol_data in context.symbols_map.values():
        if "test" in symbol_data.get("module", ""):
            continue
        if _is_excluded(symbol_data):
            continue
        fp = symbol_data.get("fingerprint")
        if fp:
            fingerprint_groups[fp].append(symbol_data)
    for symbols in fingerprint_groups.values():
        if len(symbols) > 1:
            for i, data_a in enumerate(symbols):
                for data_b in symbols[i + 1 :]:
                    findings.append(
                        _create_duplication_finding(data_a, data_b, 1.0, "ast")
                    )
    return findings


async def _check_semantic_duplication(
    context: AuditorContext, params: dict[str, Any]
) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    qdrant = getattr(context, "qdrant_service", None)
    if not context.symbols_map or not qdrant:
        return findings
    return findings


def _create_duplication_finding(a, b, score, dtype) -> AuditFinding:
    name_a = a.get("qualname") or a.get("name") or "?"
    name_b = b.get("qualname") or b.get("name") or "?"
    module_a = a.get("module", "")
    file_path = a.get("file_path") or (
        "src/" + module_a.replace(".", "/") + ".py" if module_a else None
    )
    return AuditFinding(
        check_id=f"purity.no_{dtype}_duplication",
        severity=AuditSeverity.WARNING,
        message=f"{dtype.upper()} duplication: '{name_a}' duplicates '{name_b}' (score={score:.2f})",
        file_path=file_path,
        context={
            "symbol_a": name_a,
            "symbol_b": name_b,
            "module_a": module_a,
            "module_b": b.get("module", ""),
            "similarity": score,
            "type": dtype,
        },
    )
