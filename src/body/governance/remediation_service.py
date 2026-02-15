# src/body/governance/remediation_service.py
"""
Remediation Service - Body Layer

CONSTITUTIONAL FIX: Execution logic for constitutional remediation

This service performs remediation operations (fixing violations).
It was split from ConstitutionalMonitor which violated separation by doing
both orchestration (Will) and execution (Body).

Constitutional Role:
- Body layer: Pure execution
- Receives explicit instructions on what to fix
- No decision-making about when/whether to remediate
- That's Will layer's responsibility

Migration:
- OLD: ConstitutionalMonitor (Mind layer) - orchestration + execution (VIOLATION)
- NEW: RemediationService (Body layer) - execution only (COMPLIANT)
- NEW: RemediationOrchestrator (Will layer) - orchestration only (COMPLIANT)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger
from shared.utils.header_tools import _HeaderTools


logger = getLogger(__name__)


@dataclass
# ID: da9e01ed-6964-489d-b516-91d068e5c73e
class RemediationResult:
    """Results of a remediation operation."""

    success: bool
    fixed_count: int
    failed_count: int
    error: str | None = None


@dataclass
# ID: 9da005f9-65db-4d26-acf3-2e8b79f5c39f
class Violation:
    """Represents a single constitutional violation to be remediated."""

    file_path: str
    policy_id: str
    description: str
    severity: str
    remediation_handler: str | None = None


# ID: e1084e6b-d109-4859-ac96-1d2e936e505e
# ID: 8bd6675e-f4e3-4581-90ac-74cdc2caf8a1
class RemediationService:
    """
    Body layer service for constitutional remediation execution.

    CONSTITUTIONAL COMPLIANCE:
    - Body layer: Executes remediation operations
    - NO orchestration logic (that's Will's job)
    - NO decision-making about what/when to fix
    - Receives explicit instructions and executes them

    This service is given violations and fixes them.
    It does NOT decide which violations to fix.
    """

    def __init__(self, repo_path: Path | str):
        """
        Initialize remediation service.

        Args:
            repo_path: Root path of the repository
        """
        self.repo_path = Path(repo_path)
        self.file_handler = FileHandler(str(self.repo_path))
        logger.info("RemediationService initialized for %s", self.repo_path)

    # ID: 982e1d72-919d-4608-b633-0dcb0b13847a
    # ID: f86104cc-4740-4d74-889f-6f622e1d24dc
    async def remediate_missing_headers(
        self, violations: list[Violation]
    ) -> RemediationResult:
        """
        Execute remediation for missing header violations.

        BODY LAYER EXECUTION:
        - Receives list of violations to fix
        - Does NOT decide which ones to fix (already decided by Will)
        - Executes the fixes using FileHandler
        - Reports results

        Args:
            violations: List of header violations to remediate

        Returns:
            RemediationResult with counts and status
        """
        logger.info("Executing header remediation for %d violations", len(violations))

        fixed_count = 0
        failed_count = 0
        error_messages = []

        for violation in violations:
            try:
                file_path = Path(violation.file_path)

                # Execute: Read current file
                if not file_path.exists():
                    logger.warning("File not found: %s", file_path)
                    failed_count += 1
                    continue

                current_content = file_path.read_text(encoding="utf-8")

                # Execute: Add header using HeaderTools
                updated_content = _HeaderTools.add_header_if_missing(current_content)

                # Execute: Write updated file via FileHandler (constitutional)
                if updated_content != current_content:
                    write_result = self.file_handler.write_file(
                        str(file_path), updated_content
                    )

                    if write_result.status == "success":
                        logger.info("Fixed header in: %s", file_path)
                        fixed_count += 1
                    else:
                        logger.error(
                            "Failed to write %s: %s", file_path, write_result.message
                        )
                        failed_count += 1
                        error_messages.append(f"{file_path}: {write_result.message}")
                else:
                    # Header already present, nothing to fix
                    logger.debug("Header already present in: %s", file_path)

            except Exception as e:
                logger.error("Error remediating %s: %s", violation.file_path, e)
                failed_count += 1
                error_messages.append(f"{violation.file_path}: {e!s}")

        # Report results (no decision-making)
        success = failed_count == 0
        error = "; ".join(error_messages) if error_messages else None

        logger.info(
            "Remediation complete: %d fixed, %d failed", fixed_count, failed_count
        )

        return RemediationResult(
            success=success,
            fixed_count=fixed_count,
            failed_count=failed_count,
            error=error,
        )

    # ID: 00c02bd3-4210-4e6c-9db2-907264dd3e2c
    # ID: 7d18bb42-18a0-4834-8334-be92a27f36a8
    async def remediate_single_file(self, file_path: str) -> bool:
        """
        Execute remediation for a single file.

        BODY LAYER EXECUTION:
        - Receives explicit file path to fix
        - Does NOT decide whether to fix it (already decided)
        - Executes the fix
        - Reports success/failure

        Args:
            file_path: Path to file that needs remediation

        Returns:
            True if remediation succeeded, False otherwise
        """
        try:
            path = Path(file_path)

            if not path.exists():
                logger.warning("File not found: %s", file_path)
                return False

            # Execute: Read file
            current_content = path.read_text(encoding="utf-8")

            # Execute: Add header
            updated_content = _HeaderTools.add_header_if_missing(current_content)

            # Execute: Write if changed
            if updated_content != current_content:
                write_result = self.file_handler.write_file(file_path, updated_content)

                if write_result.status == "success":
                    logger.info("Fixed header in: %s", file_path)
                    return True
                else:
                    logger.error(
                        "Failed to write %s: %s", file_path, write_result.message
                    )
                    return False
            else:
                # Already has header
                logger.debug("Header already present in: %s", file_path)
                return True

        except Exception as e:
            logger.error("Error remediating %s: %s", file_path, e)
            return False

    # ID: 036b6190-48e0-4d04-8497-4cb94ea818d1
    # ID: 0a08a917-26cb-41ea-9711-3e1335e07ed3
    def validate_remediation(self, file_path: str) -> bool:
        """
        Validate that remediation was successful for a file.

        BODY LAYER EXECUTION:
        - Checks if file now has proper header
        - Pure verification, no decision-making

        Args:
            file_path: Path to file to validate

        Returns:
            True if file has proper header, False otherwise
        """
        try:
            path = Path(file_path)

            if not path.exists():
                return False

            content = path.read_text(encoding="utf-8")
            return _HeaderTools.has_valid_header(content)

        except Exception as e:
            logger.error("Error validating %s: %s", file_path, e)
            return False


# ID: 0d79c416-b67e-446a-8795-4c8df1ed3220
# ID: aa015db1-8ed4-4017-86d9-19f1be437214
def get_remediation_service(repo_path: Path | str | None = None) -> RemediationService:
    """
    Factory function for remediation service.

    Args:
        repo_path: Optional repository path (defaults to current directory)

    Returns:
        RemediationService instance

    Usage:
        # Body layer: Execute remediation
        service = get_remediation_service()
        result = await service.remediate_missing_headers(violations)
    """
    if repo_path is None:
        repo_path = Path.cwd()

    return RemediationService(repo_path)
