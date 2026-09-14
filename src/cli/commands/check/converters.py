# src/cli/commands/check/converters.py
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
from shared.path_resolver import PathResolver
from shared.path_utils import get_repo_root


# ID: f9bbf525-5d2f-4c77-aba6-5b30e81de71b
def parse_min_severity(severity: str) -> AuditSeverity:
    """Parse severity string to AuditSeverity enum with validation."""
    try:
        return AuditSeverity[severity.upper()]
    except KeyError as exc:
        raise typer.BadParameter(
            f"Invalid severity level '{severity}'. "
            f"Must be one of: info, low, medium, high, block."
        ) from exc


# ID: cfb45511-cfe2-42c6-994e-6a618dd16104
def severity_from_string(value: str | None) -> AuditSeverity:
    """Convert lowercase string severity to enum, defaulting to BLOCK."""
    if not value:
        return AuditSeverity.BLOCK
    v = value.strip().lower()
    try:
        return AuditSeverity[v.upper()]
    except KeyError:
        return AuditSeverity.BLOCK


# ID: 97ef6873-82f3-4eb8-8bd7-b53c2130f067
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


# ID: 7a63d7bd-3365-46cb-8f4f-bd9410a7e9df
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


# ID: 04480919-8454-46d6-9202-bea018ac0563
def read_legacy_executed_ids_from_evidence() -> set[str]:
    """
    Read legacy auditor evidence to learn which checks/rules executed.

    Returns empty set if evidence is missing or invalid.
    """
    try:
        # Computed lazily — get_repo_root() raises when .intent/ is absent
        # (e.g. during BYOR onboarding before the floor has been delivered).
        evidence_path = (
            PathResolver.from_repo(get_repo_root()).reports_dir
            / "audit"
            / "latest_audit.json"
        )
        if not evidence_path.exists():
            return set()
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        executed = payload.get("executed_checks", [])
        if not isinstance(executed, list):
            return set()
        return {str(x).strip() for x in executed if isinstance(x, str) and x.strip()}
    except Exception:
        return set()
