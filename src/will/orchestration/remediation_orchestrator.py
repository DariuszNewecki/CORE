# src/will/orchestration/remediation_orchestrator.py

"""
Remediation Orchestrator - Will Layer

CONSTITUTIONAL FIX: Orchestration logic for constitutional remediation

This orchestrator makes decisions about remediation (what/when to fix).
It was split from ConstitutionalMonitor which violated separation by doing
both orchestration (Will) and execution (Body).

Constitutional Role:
- Will layer: Decision-making and orchestration
- Decides what needs remediation
- Decides when to remediate
- Delegates execution to Body layer
- No direct file operations

Migration:
- OLD: ConstitutionalMonitor (Mind layer) - orchestration + execution (VIOLATION)
- NEW: RemediationOrchestrator (Will layer) - orchestration only (COMPLIANT)
- NEW: RemediationService (Body layer) - execution only (COMPLIANT)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from body.governance.remediation_service import (
    RemediationResult,
    RemediationService,
    Violation,
)
from mind.governance.audit_context import AuditorContext
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: e5a475b7-8ba0-4165-924a-978932779f33
# ID: e6f558e7-0ce7-41c8-9612-82a0c2c3f0ab
class KnowledgeGraphBuilderProtocol(Protocol):
    """Protocol for knowledge graph builder dependency."""

    # ID: 2deaf085-c14c-4f34-aa18-a660ef8aa43e
    async def build_and_sync(self) -> None: ...


@dataclass
# ID: d71e2192-e8d9-46d9-8cf1-d7ac20fa6bce
# ID: 835e78b0-af57-4a86-a29a-5bfc4dc7fbbe
class AuditReport:
    """Results of a constitutional audit."""

    policy_category: str
    violations: list[Violation]
    total_files_scanned: int
    compliant_files: int

    @property
    # ID: 418475ad-bdd8-46c2-a353-0be5976319b1
    def has_violations(self) -> bool:
        return len(self.violations) > 0


# ID: 81dec550-5f47-4d3c-8636-578b1188bff3
# ID: f1a2b3c4-d5e6-7f8a-9b0c-1d2e3f4a5b6c
class RemediationOrchestrator:
    """
    Will layer orchestrator for constitutional remediation.

    CONSTITUTIONAL COMPLIANCE:
    - Will layer: Makes decisions and orchestrates
    - Decides what to audit
    - Decides what to remediate
    - Delegates execution to Body layer
    - NO direct file operations (that's Body's job)

    This orchestrator decides strategy and delegates execution.
    It does NOT execute remediation itself.
    """

    def __init__(
        self,
        repo_path: Path | str,
        knowledge_builder: KnowledgeGraphBuilderProtocol | None = None,
    ):
        """
        Initialize remediation orchestrator.

        Args:
            repo_path: Root path of the repository to orchestrate
            knowledge_builder: Optional knowledge graph builder for post-remediation
        """
        self.repo_path = Path(repo_path)
        self.knowledge_builder = knowledge_builder

        # Will layer: Use Mind layer for auditing (reads governance)
        self.auditor = AuditorContext(self.repo_path)

        # Will layer: Use Body layer for execution (does work)
        self.remediation_service = RemediationService(self.repo_path)

        logger.info("RemediationOrchestrator initialized for %s", self.repo_path)

    # ID: f6c38535-eea4-4a83-87a4-257bf40b3d48
    # ID: de325a31-c034-401f-94f9-fb3a11899511
    def audit_headers(self) -> AuditReport:
        """
        ORCHESTRATION: Decide to audit headers and collect results.

        Will layer responsibility:
        - Decides to run audit
        - Collects results from Mind layer (AuditorContext)
        - Formats results for decision-making
        - Does NOT execute audit itself

        Returns:
            AuditReport with violations found
        """
        logger.info("Orchestrating header audit...")

        # Decision: Audit all Python files
        violations_found: list[Violation] = []
        total_scanned = 0
        compliant = 0

        # Delegate to Mind layer: Get audit results
        src_path = self.repo_path / "src"
        if src_path.exists():
            for py_file in src_path.rglob("*.py"):
                total_scanned += 1

                # Mind layer tells us: Does this file have violations?
                has_violation = self.auditor.check_file_header(str(py_file))

                if has_violation:
                    # Decision: Record this as needing remediation
                    violations_found.append(
                        Violation(
                            file_path=str(py_file),
                            policy_id="code.headers.required",
                            description="Missing required header",
                            severity="warning",
                            remediation_handler="add_header",
                        )
                    )
                else:
                    compliant += 1

        logger.info(
            "Audit complete: %d scanned, %d violations, %d compliant",
            total_scanned,
            len(violations_found),
            compliant,
        )

        return AuditReport(
            policy_category="headers",
            violations=violations_found,
            total_files_scanned=total_scanned,
            compliant_files=compliant,
        )

    # ID: 6dd9b2bb-1810-46d9-9c1d-6dbb4d4b2aaf
    # ID: b3c4d5e6-f7a8-9b0c-1d2e-3f4a5b6c7d8e
    async def remediate_missing_headers_async(self) -> RemediationResult:
        """
        ORCHESTRATION: Decide to remediate headers and coordinate execution.

        Will layer responsibility:
        - Decides to find violations (calls audit)
        - Decides to remediate them
        - Delegates execution to Body layer
        - Decides post-remediation actions (knowledge graph update)
        - Does NOT execute remediation itself

        Returns:
            RemediationResult with execution results from Body layer
        """
        logger.info("Orchestrating header remediation...")

        # Decision 1: Audit to find violations
        audit_report = self.audit_headers()

        if not audit_report.has_violations:
            logger.info("No violations found, no remediation needed")
            return RemediationResult(
                success=True, fixed_count=0, failed_count=0, error=None
            )

        logger.info("Found %d violations to remediate", len(audit_report.violations))

        # Decision 2: Delegate execution to Body layer
        result = await self.remediation_service.remediate_missing_headers(
            audit_report.violations
        )

        # Decision 3: Update knowledge graph if remediation succeeded
        if result.success and self.knowledge_builder:
            logger.info("Orchestrating knowledge graph update after remediation...")
            try:
                await self.knowledge_builder.build_and_sync()
                logger.info("Knowledge graph updated successfully")
            except Exception as e:
                logger.error("Failed to update knowledge graph: %s", e)
                # Don't fail the whole operation if KG update fails

        logger.info(
            "Remediation orchestration complete: %d fixed, %d failed",
            result.fixed_count,
            result.failed_count,
        )

        return result

    # ID: 69a3a3fc-4128-4f81-a1e2-3350e614a5f0
    # ID: c4d5e6f7-a8b9-0c1d-2e3f-4a5b6c7d8e9f
    async def remediate_single_file_async(self, file_path: str) -> bool:
        """
        ORCHESTRATION: Decide to remediate single file and delegate execution.

        Will layer responsibility:
        - Decides to remediate specific file
        - Delegates execution to Body layer
        - Decides whether to update knowledge graph
        - Does NOT execute remediation itself

        Args:
            file_path: Path to file to remediate

        Returns:
            True if remediation succeeded, False otherwise
        """
        logger.info("Orchestrating remediation for: %s", file_path)

        # Decision 1: Delegate execution to Body layer
        success = await self.remediation_service.remediate_single_file(file_path)

        # Decision 2: Update knowledge graph if needed
        if success and self.knowledge_builder:
            logger.info("Orchestrating knowledge graph update for: %s", file_path)
            try:
                await self.knowledge_builder.build_and_sync()
            except Exception as e:
                logger.error("Failed to update knowledge graph: %s", e)

        return success

    # ID: 97bbb28e-2153-45d2-b5f7-e84bc36d616a
    # ID: d5e6f7a8-b9c0-1d2e-3f4a-5b6c7d8e9f0a
    def validate_remediation(self, file_path: str) -> bool:
        """
        ORCHESTRATION: Decide to validate remediation and delegate check.

        Will layer responsibility:
        - Decides to validate specific file
        - Delegates validation to Body layer
        - Does NOT execute validation itself

        Args:
            file_path: Path to file to validate

        Returns:
            True if file is compliant, False otherwise
        """
        logger.info("Orchestrating validation for: %s", file_path)

        # Delegate to Body layer
        return self.remediation_service.validate_remediation(file_path)


# ID: 869efd85-5202-441b-a92a-987386ada48c
# ID: e6f7a8b9-c0d1-2e3f-4a5b-6c7d8e9f0a1b
def get_remediation_orchestrator(
    repo_path: Path | str | None = None,
    knowledge_builder: KnowledgeGraphBuilderProtocol | None = None,
) -> RemediationOrchestrator:
    """
    Factory function for remediation orchestrator.

    Args:
        repo_path: Optional repository path (defaults to current directory)
        knowledge_builder: Optional knowledge graph builder

    Returns:
        RemediationOrchestrator instance

    Usage:
        # Will layer: Orchestrate remediation
        orchestrator = get_remediation_orchestrator()
        result = await orchestrator.remediate_missing_headers_async()
    """
    if repo_path is None:
        repo_path = Path.cwd()

    return RemediationOrchestrator(repo_path, knowledge_builder)
