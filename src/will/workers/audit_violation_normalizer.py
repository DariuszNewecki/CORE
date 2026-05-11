# src/will/workers/audit_violation_normalizer.py
"""
Audit-output normalization for AuditViolationSensor.

This module owns the auditor's output contract: it invokes
mind.governance.filtered_audit.run_filtered_audit, walks the raw
findings, normalises dict-vs-object differences, and runs the
fallback file-path recovery heuristic for findings that arrive
without a resolved file_path (symbol-pair findings, project-scope
findings).

When the auditor's output format evolves (a new field on
AuditFinding, a smarter symbol-pair recovery path, a new fallback for
unresolvable paths), this is the module that changes.

LAYER: will/workers — collaborator of AuditViolationSensor. No DB writes
or file writes. DB access for the audit run is via service_registry
session, matching the prior in-method behaviour.
"""

from __future__ import annotations

from typing import Any

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 41db6caf-ebc0-4996-8b54-104c0634c165
async def normalize_audit_findings(
    core_context: Any,
    rule_namespace: str,
    rule_ids: list[str],
) -> list[dict[str, Any]]:
    """
    Run a filtered constitutional audit for the resolved rule IDs and
    return normalized violation dicts.

    Each returned dict has keys: file_path, line_number, message,
    severity, rule_id, context. When the auditor emits a finding without
    a real file_path (symbol-pair findings, project-scope findings),
    this function attempts a fallback recovery via context.symbol_a and
    auditor_context.symbols_map; if no path can be recovered, it
    synthesizes a sentinel of the form "__symbol_pair__<symbol>" that
    the downstream filter recognises as unactionable.
    """
    from body.services.service_registry import service_registry
    from mind.governance.filtered_audit import run_filtered_audit

    auditor_context = core_context.auditor_context

    async with service_registry.session() as session:
        auditor_context.db_session = session
        await auditor_context.load_knowledge_graph()
        raw_findings, _, _ = await run_filtered_audit(
            auditor_context, rule_ids=rule_ids
        )
        auditor_context.db_session = None

    violations = []
    for finding in raw_findings:
        if isinstance(finding, dict):
            file_path = finding.get("file_path")
            message = finding.get("message", "")
            severity = str(finding.get("severity", "warning"))
            line_number = finding.get("line_number")
            rule_id = finding.get("check_id", rule_namespace)
            ctx = finding.get("context", {})
        else:
            file_path = getattr(finding, "file_path", None)
            message = getattr(finding, "message", "")
            severity = str(getattr(finding, "severity", "warning"))
            line_number = getattr(finding, "line_number", None)
            rule_id = getattr(finding, "check_id", rule_namespace)
            ctx = getattr(finding, "context", {}) or {}

        if not file_path:
            symbol_a = ctx.get("symbol_a", "")
            file_path = (
                ctx.get("file_path") or ctx.get("file") or ctx.get("module_path")
            )
            if not file_path and symbol_a:
                symbols_map = getattr(core_context.auditor_context, "symbols_map", {})
                for sym_path, sym_data in symbols_map.items():
                    qualname = sym_data.get("qualname", "") or sym_data.get("name", "")
                    if qualname == symbol_a or sym_path.endswith(f".{symbol_a}"):
                        module = sym_data.get("module", "")
                        if module:
                            file_path = "src/" + module.replace(".", "/") + ".py"
                        break

            if not file_path:
                file_path = f"__symbol_pair__{ctx.get('symbol_a', 'unknown')}"

        violations.append(
            {
                "file_path": file_path,
                "line_number": line_number,
                "message": message,
                "severity": severity,
                "rule_id": rule_id,
                "context": ctx,
            }
        )

    return violations
