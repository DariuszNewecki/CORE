# src/body/cli/commands/check/converters.py
"""
Data converters for audit results.

Handles conversion between different audit finding formats:
- Engine findings (dicts) -> AuditFinding objects
- String severities -> AuditSeverity enums
- File path resolution
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from shared.models import AuditFinding, AuditSeverity
from shared.path_utils import get_repo_root


# Evidence artifact written by legacy governance auditor
LEGACY_AUDIT_EVIDENCE_PATH = get_repo_root() / "reports" / "audit" / "latest_audit.json"


# ID: a9b8c7d6-e5f4-3a2b-1c0d-9e8f7a6b5c4d
def parse_min_severity(severity: str) -> AuditSeverity:
    """Parse severity string to AuditSeverity enum with validation."""
    try:
        return AuditSeverity[severity.upper()]
    except KeyError as exc:
        raise typer.BadParameter(
            f"Invalid severity level '{severity}'. Must be 'info', 'warning', or 'error'."
        ) from exc


# ID: b8c7d6e5-f4a3-2b1c-0d9e-8f7a6b5c4d3e
def severity_from_string(value: str | None) -> AuditSeverity:
    """Convert string severity to enum, defaulting to ERROR."""
    if not value:
        return AuditSeverity.ERROR
    v = value.strip().lower()
    if v == "info":
        return AuditSeverity.INFO
    if v == "warning":
        return AuditSeverity.WARNING
    if v == "error":
        return AuditSeverity.ERROR
    return AuditSeverity.ERROR


# ID: c7d6e5f4-a3b2-1c0d-9e8f-7a6b5c4d3e2f
def convert_engine_findings_to_audit_findings(
    *,
    file_path: Path,
    engine_findings: list[dict],
    tag_check_ids: bool,
) -> list[AuditFinding]:
    """
    Convert engine-based auditor findings (dicts) to AuditFinding objects.

    Args:
        file_path: Source file path for findings
        engine_findings: List of finding dicts from engine
        tag_check_ids: If True, prefix check_id with "v2:" for hybrid output

    Returns:
        List of AuditFinding objects
    """
    converted: list[AuditFinding] = []
    for f in engine_findings:
        rule_id = str(f.get("rule_id") or "unknown")
        engine = str(f.get("engine") or "").strip()
        message = str(f.get("message") or "Violation")
        severity = severity_from_string(f.get("severity"))

        check_id = f"v2:{rule_id}" if tag_check_ids else rule_id
        if engine:
            message = f"[{engine}] {message}"

        converted.append(
            AuditFinding(
                check_id=check_id,
                severity=severity,
                message=message,
                file_path=str(file_path),
                line_number=None,
            )
        )
    return converted


# ID: d6e5f4a3-b2c1-0d9e-8f7a-6b5c4d3e2f1a
def convert_finding_dicts_to_models(findings_dicts: list[dict]) -> list[AuditFinding]:
    """
    Convert finding dictionaries to AuditFinding model objects.

    Handles severity string -> enum conversion.
    """
    severity_map = {str(s): s for s in AuditSeverity}
    findings = []

    for f_dict in findings_dicts:
        severity_val = f_dict.get("severity", "info")
        if isinstance(severity_val, str):
            f_dict["severity"] = severity_map.get(severity_val, AuditSeverity.INFO)
        findings.append(AuditFinding(**f_dict))

    return findings


# ID: e5f4a3b2-c1d0-9e8f-7a6b-5c4d3e2f1a0b
def read_legacy_executed_ids_from_evidence() -> set[str]:
    """
    Read legacy auditor evidence to learn which checks/rules executed.

    Returns empty set if evidence is missing or invalid.
    """
    try:
        if not LEGACY_AUDIT_EVIDENCE_PATH.exists():
            return set()
        payload = json.loads(LEGACY_AUDIT_EVIDENCE_PATH.read_text(encoding="utf-8"))
        executed = payload.get("executed_checks", [])
        if not isinstance(executed, list):
            return set()
        return {str(x).strip() for x in executed if isinstance(x, str) and x.strip()}
    except Exception:
        return set()
