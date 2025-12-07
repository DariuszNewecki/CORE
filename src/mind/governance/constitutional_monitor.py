# src/mind/governance/constitutional_monitor.py

"""
Constitutional Monitor - Mind-layer orchestrator for constitutional compliance auditing.

This module provides high-level constitutional governance operations by coordinating
between AuditorContext and remediation handlers. It implements the Mind layer's
responsibility for decision-making about constitutional violations.

ID: 8f4a3b2c-9d1e-4f5a-8b2c-3d4e5f6a7b8c
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from shared.logger import getLogger
from shared.utils.header_tools import _HeaderTools

from mind.governance.audit_context import AuditorContext

logger = getLogger(__name__)


# ID: c5cb0280-d917-4098-a200-43de6a15de29
class KnowledgeGraphBuilderProtocol(Protocol):
    # ID: f9b3a36a-3c6e-4eff-a645-48c5c5135573
    async def build_and_sync(self) -> None: ...


@dataclass
# ID: e0d28190-86da-4719-9a2d-a38dcedadfa1
class Violation:
    """Represents a single constitutional violation."""

    file_path: str
    policy_id: str
    description: str
    severity: str
    remediation_handler: str | None = None


@dataclass
# ID: c909253f-28a4-4b29-9c50-cb4b30df3dba
class AuditReport:
    """Results of a constitutional audit."""

    policy_category: str
    violations: list[Violation]
    total_files_scanned: int
    compliant_files: int

    @property
    # ID: c603c676-9db7-4c0f-99d8-06a581270f22
    def has_violations(self) -> bool:
        return len(self.violations) > 0


@dataclass
# ID: 2eb4e4cf-9dbe-4806-8618-4e819ac6b89a
class RemediationResult:
    """Results of constitutional remediation."""

    success: bool
    fixed_count: int
    failed_count: int
    error: str | None = None


# ID: 40dae6d4-c0e7-45a6-bd53-4768a19aff60
class ConstitutionalMonitor:
    """
    Mind-layer orchestrator for constitutional compliance and remediation.

    This class coordinates between AuditorContext and autonomous remediation,
    using the HeaderTools for actual header manipulation.
    """

    def __init__(
        self,
        repo_path: Path | str,
        knowledge_builder: KnowledgeGraphBuilderProtocol | None = None,
    ):
        """
        Initialize the constitutional monitor.

        Args:
            repo_path: Root path of the repository to monitor
            knowledge_builder: Optional knowledge graph builder for post-remediation updates
        """
        self.repo_path = Path(repo_path)
        self.auditor = AuditorContext(self.repo_path)
        self.knowledge_builder = knowledge_builder
        logger.info(f"ConstitutionalMonitor initialized for {self.repo_path}")

    # ID: 25eeb765-56da-4101-86e4-65d9fb4ea68b
    def audit_headers(self) -> AuditReport:
        """
        Audit all Python files for header compliance.

        Returns:
            AuditReport containing all header violations found
        """
        logger.info("Starting constitutional header audit...")
        all_py_files = [
            str(p.relative_to(self.repo_path))
            for p in (self.repo_path / "src").rglob("*.py")
        ]
        logger.info(f"Scanning {len(all_py_files)} files for header compliance...")
        violation_objects = []
        for file_path_str in all_py_files:
            file_path = self.repo_path / file_path_str
            try:
                original_content = file_path.read_text(encoding="utf-8")
                header = _HeaderTools.parse(original_content)
                correct_location_comment = f"# {file_path_str}"
                is_compliant = (
                    header.location == correct_location_comment
                    and header.module_description is not None
                    and header.has_future_import
                )
                if not is_compliant:
                    violations = []
                    if header.location != correct_location_comment:
                        violations.append("incorrect file location comment")
                    if not header.module_description:
                        violations.append("missing module docstring")
                    if not header.has_future_import:
                        violations.append("missing __future__ import")
                    violation_objects.append(
                        Violation(
                            file_path=file_path_str,
                            policy_id="header_compliance",
                            description=f"Header violations: {', '.join(violations)}",
                            severity="medium",
                            remediation_handler="fix_header",
                        )
                    )
            except Exception as e:
                logger.warning("Could not process {file_path_str}: %s", e)
        compliant = len(all_py_files) - len(violation_objects)
        logger.info(
            f"Header audit complete: {len(violation_objects)} violations across {len(all_py_files)} files"
        )
        return AuditReport(
            policy_category="header_compliance",
            violations=violation_objects,
            total_files_scanned=len(all_py_files),
            compliant_files=compliant,
        )

    # ID: 585abcab-4b96-4889-ba96-0b408db0755a
    def remediate_violations(self, audit_report: AuditReport) -> RemediationResult:
        """
        Trigger autonomous remediation for constitutional violations.

        Args:
            audit_report: The audit report containing violations to fix

        Returns:
            RemediationResult with success status and counts
        """
        if not audit_report.violations:
            logger.info("No violations to remediate")
            return RemediationResult(success=True, fixed_count=0, failed_count=0)
        logger.info(
            f"Starting remediation for {len(audit_report.violations)} violations..."
        )
        fixed_count = 0
        failed_count = 0
        for violation in audit_report.violations:
            try:
                if violation.remediation_handler == "fix_header":
                    success = self._remediate_header_violation(violation)
                    if success:
                        fixed_count += 1
                    else:
                        failed_count += 1
                else:
                    logger.warning(
                        f"No remediation handler for {violation.remediation_handler}"
                    )
                    failed_count += 1
            except Exception as e:
                logger.error("Failed to remediate {violation.file_path}: %s", e)
                failed_count += 1
        if fixed_count > 0 and self.knowledge_builder:
            logger.info("🧠 Rebuilding knowledge graph to reflect all changes...")
            asyncio.run(self.knowledge_builder.build_and_sync())
            logger.info("✅ Knowledge graph successfully updated.")
        logger.info(
            "Remediation complete: {fixed_count} fixed, %s failed", failed_count
        )
        return RemediationResult(
            success=failed_count == 0,
            fixed_count=fixed_count,
            failed_count=failed_count,
            error=None if failed_count == 0 else f"{failed_count} violations failed",
        )

    def _remediate_header_violation(self, violation: Violation) -> bool:
        """
        Fix a single header violation using HeaderTools.

        Args:
            violation: The violation to fix

        Returns:
            True if successfully fixed, False otherwise
        """
        try:
            file_path = self.repo_path / violation.file_path
            original_content = file_path.read_text(encoding="utf-8")
            header = _HeaderTools.parse(original_content)
            correct_location_comment = f"# {violation.file_path}"
            header.location = correct_location_comment
            if not header.module_description:
                header.module_description = (
                    f'"""Provides functionality for the {file_path.stem} module."""'
                )
            header.has_future_import = True
            corrected_code = _HeaderTools.reconstruct(header)
            if corrected_code != original_content:
                file_path.write_text(corrected_code, "utf-8")
                logger.info(f"Fixed header in {violation.file_path}")
                return True
            else:
                logger.debug(f"No changes needed for {violation.file_path}")
                return True
        except Exception as e:
            logger.error("Failed to fix header in {violation.file_path}: %s", e)
            return False
