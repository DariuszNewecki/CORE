# src/features/governance/constitutional_auditor.py
"""
The Constitutional Auditor is the primary enforcement mechanism for the CORE constitution.
It runs a series of checks to ensure the codebase and its declared intent are aligned.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, List, Tuple

from rich.console import Console

from features.governance.audit_context import AuditorContext
from features.governance.checks.capability_coverage import CapabilityCoverageCheck
from features.governance.checks.domain_placement import DomainPlacementCheck
from features.governance.checks.duplication_check import DuplicationCheck
from features.governance.checks.environment_checks import EnvironmentChecks
from features.governance.checks.file_checks import FileChecks
from features.governance.checks.health_checks import HealthChecks
from features.governance.checks.id_coverage_check import IdCoverageCheck
from features.governance.checks.import_rules import ImportRulesCheck
from features.governance.checks.knowledge_source_check import KnowledgeSourceCheck
from features.governance.checks.manifest_lint import ManifestLintCheck
from features.governance.checks.naming_conventions import NamingConventionsCheck
from features.governance.checks.orphaned_logic import OrphanedLogicCheck
from features.governance.checks.security_checks import SecurityChecks
from features.governance.checks.style_checks import StyleChecks
from shared.logger import getLogger
from shared.models import AuditFinding

log = getLogger("constitutional_auditor")
console = Console()


# ID: 5e27884e-b01e-4861-84b0-2e8c8facdb74
class ConstitutionalAuditor:
    """Orchestrates all constitutional checks and reports the findings."""

    def __init__(self, repo_root_override: Path | None = None):
        self.repo_root = repo_root_override or Path(".").resolve()
        self.context = AuditorContext(self.repo_root)
        self.checks: List[Any] = []

    async def _initialize_checks(self):
        """Initializes all checks after the context has loaded its async data."""
        await self.context.load_knowledge_graph()
        self.checks = [
            FileChecks(self.context),
            EnvironmentChecks(self.context),
            HealthChecks(self.context),
            StyleChecks(self.context),
            SecurityChecks(self.context),
            CapabilityCoverageCheck(self.context),
            DomainPlacementCheck(self.context),
            ManifestLintCheck(self.context),
            ImportRulesCheck(self.context),
            NamingConventionsCheck(self.context),
            OrphanedLogicCheck(self.context),
            DuplicationCheck(self.context),
            KnowledgeSourceCheck(self.context),
            IdCoverageCheck(self.context),  # Add the new check
        ]
        log.info(f"ConstitutionalAuditor initialized with {len(self.checks)} checks.")

    # ID: fcbf94ee-eb92-4c49-8c84-7b5b2aeff2ff
    async def run_full_audit_async(self) -> Tuple[bool, List[AuditFinding], int]:
        """Asynchronously runs all registered checks and returns the results."""
        if not self.checks:
            await self._initialize_checks()

        all_findings: List[AuditFinding] = []
        for check in self.checks:
            try:
                if isinstance(check, DuplicationCheck):
                    findings = await check.execute()
                else:
                    findings = check.execute()
                all_findings.extend(findings)
            except Exception as e:
                log.error(
                    f"Error executing check '{type(check).__name__}': {e}",
                    exc_info=True,
                )

        unassigned_symbols_count = len(
            OrphanedLogicCheck(self.context).find_unassigned_public_symbols()
        )

        has_errors = any(f.severity.is_blocking for f in all_findings)
        return not has_errors, all_findings, unassigned_symbols_count

    # ID: 0c850a95-21f6-4a54-8c23-f731e8eb4a8f
    def run_full_audit(self) -> Tuple[bool, List[AuditFinding], int]:
        """Synchronous wrapper to run the full async audit."""
        return asyncio.run(self.run_full_audit_async())
