# src/mind/governance/audit_postprocessor.py
"""
Post-processing utilities for Constitutional Auditor findings.

This module provides:
  1) Severity downgrade for dead-public-symbol findings when the symbol
     has an allowed entry_point_type
  2) Auto-generated reports of all symbols auto-ignored-by-pattern

CONSTITUTIONAL FIX: No longer imports FileHandler directly.
Uses FileService from Body layer for all file operations.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, MutableMapping, Sequence
from pathlib import Path

from body.services.file_service import FileService
from mind.governance.audit_report_writer import write_auto_ignored_reports
from mind.governance.entry_point_policy import EntryPointAllowList
from mind.governance.finding_processor import process_findings_with_downgrade


# ID: 3bd0eccd-bc48-4d04-88d4-bd4d9ae4fa14
def apply_entry_point_downgrade_and_report(
    *,
    findings: Sequence[MutableMapping[str, object]],
    symbol_index: Mapping[str, Mapping[str, object]],
    reports_dir: str | Path = "reports",
    allow_list: EntryPointAllowList | None = None,
    dead_rule_ids: Iterable[str] = ("dead_public_symbol", "dead-public-symbol"),
    downgrade_to: str = "info",
    write_reports: bool = True,
    file_service: FileService | None = None,
    repo_root: Path | None = None,
) -> list[MutableMapping[str, object]]:
    """
    Process audit findings with entry point downgrade and optional reporting.

    CONSTITUTIONAL FIX: Changed parameter from FileHandler to FileService

    Args:
        findings: List of audit findings to process
        symbol_index: Mapping of symbol keys to metadata
        reports_dir: Directory for report output
        allow_list: Entry point types that should be downgraded
        dead_rule_ids: Rule IDs identifying dead-public-symbol findings
        downgrade_to: Target severity level (info/warn)
        write_reports: Whether to generate reports
        file_service: FileService for constitutional compliance (required if write_reports=True)
        repo_root: Repository root path (required if write_reports=True)

    Returns:
        List of processed findings (may be mutated in place)

    Raises:
        ValueError: If write_reports=True but file_service or repo_root not provided
    """
    allow = allow_list or EntryPointAllowList.default()

    processed, auto_ignored = process_findings_with_downgrade(
        findings=findings,
        symbol_index=symbol_index,
        allow_list=allow,
        dead_rule_ids=dead_rule_ids,
        downgrade_to=downgrade_to,
    )

    if write_reports:
        if file_service is None:
            raise ValueError(
                "write_reports=True requires file_service (constitutional compliance)"
            )

        resolved_repo_root = repo_root or getattr(file_service, "repo_path", None)
        if not isinstance(resolved_repo_root, Path):
            raise ValueError(
                "repo_root could not be determined; pass repo_root explicitly"
            )

        write_auto_ignored_reports(
            repo_root=resolved_repo_root,
            file_service=file_service,
            reports_dir=reports_dir,
            auto_ignored=auto_ignored,
        )

    return processed
