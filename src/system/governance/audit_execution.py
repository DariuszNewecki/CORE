# src/system/governance/audit_execution.py
"""
Execution engine for constitutional audit checks.

This module handles the execution of discovered audit checks, including error handling,
logging integration, and result reporting. It provides a clean separation between
check discovery, execution, and reporting phases.
"""

from __future__ import annotations

import io
from typing import Callable, List, Tuple

from rich.console import Console
from rich.panel import Panel

from shared.logger import getLogger
from system.governance.models import AuditFinding, AuditSeverity

from .audit_context import AuditorContext

log = getLogger(__name__)


# CAPABILITY: audit.execute.full
class AuditExecutor:
    """Handles the execution of constitutional audit checks."""

    class _LoggingBridge(io.StringIO):
        """Redirects console output to the logger."""

        def write(self, s: str) -> None:
            """
            Redirects writes to the logger info stream.

            Args:
                s: String content to write to the logger.
            """
            if cleaned_s := s.strip():
                log.info(cleaned_s)

    # CAPABILITY: system.audit.executor.initialize
    def __init__(self, context: AuditorContext):
        """
        Initialize the audit executor.

        Args:
            context: Shared audit context containing repository state and configuration.
        """
        self.context = context
        self.console = Console(
            file=self._LoggingBridge(), force_terminal=True, color_system="auto"
        )

    # CAPABILITY: audit.execute.checks
    def execute_checks(self, checks: List[Tuple[str, Callable]]) -> List[AuditFinding]:
        """
        Execute all provided audit checks and collect findings.

        Args:
            checks: List of tuples containing check names and callable functions.

        Returns:
            List of audit findings from all executed checks.
        """
        findings: List[AuditFinding] = []

        for check_name, check_fn in checks:
            short_name = check_name.split(":")[0]
            log.info(f"🔍 Running Check: {short_name}")
            try:
                check_findings = check_fn()
                if check_findings:
                    findings.extend(check_findings)
                    for finding in check_findings:
                        self._log_finding(finding)
            except Exception as e:
                log.error(
                    f"💥 Check '{check_name}' failed unexpectedly: {e}", exc_info=True
                )
                findings.append(
                    AuditFinding(
                        severity=AuditSeverity.ERROR,
                        message=f"Check failed: {e}",
                        check_name=check_name,
                    )
                )

        return findings

    # CAPABILITY: system.audit.log_finding
    def _log_finding(self, finding: AuditFinding) -> None:
        """
        Log an individual audit finding with appropriate severity level.

        Args:
            finding: The audit finding to log.
        """
        match finding.severity:
            case AuditSeverity.ERROR:
                log.error(f"❌ {finding.message}")
            case AuditSeverity.WARNING:
                log.warning(f"⚠️ {finding.message}")
            case AuditSeverity.SUCCESS:
                log.info(f"✅ {finding.message}")

    # CAPABILITY: audit.report.final_status
    def report_final_status(
        self, findings: List[AuditFinding], passed: bool, symbols_list: list
    ) -> None:
        """
        Print final audit summary to the console, including the unassigned capability count.

        Args:
            findings: List of all audit findings to summarize.
            passed: Whether all checks passed without errors.
            symbols_list: The list of all symbols from the knowledge graph.
        """
        errors = sum(1 for f in findings if f.severity == AuditSeverity.ERROR)
        warnings = sum(1 for f in findings if f.severity == AuditSeverity.WARNING)
        unassigned_count = sum(
            1
            for s in symbols_list
            if s.get("capability") == "unassigned" and not s.get("parent_class_key")
        )

        summary_text = (
            f"Errors: {errors}\n"
            f"Warnings: {warnings}\n"
            f"Unassigned Capabilities: {unassigned_count}"
        )

        if passed:
            title = "✅ ALL CHECKS PASSED"
            style = "bold green"
        else:
            title = "❌ AUDIT FAILED"
            style = "bold red"

        self.console.print(Panel(summary_text, title=title, style=style, expand=False))
