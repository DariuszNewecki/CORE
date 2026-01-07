# src/mind/governance/constitutional_monitor.py

"""
Constitutional Monitor - Mind-layer orchestrator for constitutional compliance auditing.

This module provides high-level constitutional governance operations by coordinating
between AuditorContext and remediation handlers. It implements the Mind layer's
responsibility for decision-making about constitutional violations.

CONSTITUTIONAL FIX:
- Aligned with 'governance.artifact_mutation.traceable'.
- Replaced direct Path writes with governed FileHandler mutations.
- Enforces IntentGuard and audit logging for all header remediations.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from mind.governance.audit_context import AuditorContext
from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger
from shared.utils.header_tools import _HeaderTools


logger = getLogger(__name__)


# ID: e6f558e7-0ce7-41c8-9612-82a0c2c3f0ab
class KnowledgeGraphBuilderProtocol(Protocol):
    # ID: 28aecdd5-ffb5-4924-9828-55adfce438a2
    async def build_and_sync(self) -> None: ...


@dataclass
# ID: 9da005f9-65db-4d26-acf3-2e8b79f5c39f
class Violation:
    """Represents a single constitutional violation."""

    file_path: str
    policy_id: str
    description: str
    severity: str
    remediation_handler: str | None = None


@dataclass
# ID: 835e78b0-af57-4a86-a29a-5bfc4dc7fbbe
class AuditReport:
    """Results of a constitutional audit."""

    policy_category: str
    violations: list[Violation]
    total_files_scanned: int
    compliant_files: int

    @property
    # ID: dc6f0026-b443-4cb0-89a5-5fae9680241b
    def has_violations(self) -> bool:
        return len(self.violations) > 0


@dataclass
# ID: da9e01ed-6964-489d-b516-91d068e5c73e
class RemediationResult:
    """Results of constitutional remediation."""

    success: bool
    fixed_count: int
    failed_count: int
    error: str | None = None


# ID: 92f0a6fd-f647-4248-9776-26f2eefc9b1c
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

        # CONSTITUTIONAL FIX: Use FileHandler for all mutations
        self.file_handler = FileHandler(str(self.repo_path))

        logger.info("ConstitutionalMonitor initialized for %s", self.repo_path)

    # ID: dae8dd95-0ac1-4a96-8ef8-92a4326499b1
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
        logger.info("Scanning %s files for header compliance...", len(all_py_files))
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
                logger.warning("Could not process %s: %s", file_path_str, e)
        compliant = len(all_py_files) - len(violation_objects)
        logger.info(
            "Header audit complete: %s violations across %s files",
            len(violation_objects),
            len(all_py_files),
        )
        return AuditReport(
            policy_category="header_compliance",
            violations=violation_objects,
            total_files_scanned=len(all_py_files),
            compliant_files=compliant,
        )

    # ID: 9245ffe5-a981-4fd3-818c-7efd7171c189
    async def remediate_violations(
        self, audit_report: AuditReport
    ) -> RemediationResult:
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
            "Starting remediation for %s violations...", len(audit_report.violations)
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
                        "No remediation handler for %s", violation.remediation_handler
                    )
                    failed_count += 1
            except Exception as e:
                logger.error("Failed to remediate %s: %s", violation.file_path, e)
                failed_count += 1
        if fixed_count > 0 and self.knowledge_builder:
            logger.info("🧠 Rebuilding knowledge graph to reflect all changes...")
            await self.knowledge_builder.build_and_sync()
            logger.info("✅ Knowledge graph successfully updated.")
        logger.info(
            "Remediation complete: %s fixed, %s failed", fixed_count, failed_count
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
                # CONSTITUTIONAL FIX: Use governed mutation surface instead of Path.write_text
                # Relativization and IntentGuard checks are performed by the FileHandler.
                self.file_handler.write_runtime_text(
                    violation.file_path, corrected_code
                )
                logger.info("Fixed header in %s", violation.file_path)
                return True
            else:
                logger.debug("No changes needed for %s", violation.file_path)
                return True
        except Exception as e:
            logger.error("Failed to fix header in %s: %s", violation.file_path, e)
            return False
