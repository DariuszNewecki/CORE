# src/mind/governance/constitutional_monitor.py

"""
Constitutional Monitor - BACKWARD COMPATIBILITY WRAPPER

CONSTITUTIONAL FIX: This file is now a thin wrapper that delegates to the new architecture.

OLD (VIOLATION):
- ConstitutionalMonitor in Mind layer did both orchestration AND execution
- Mind layer executed remediation (constitutional violation)

NEW (COMPLIANT):
- RemediationOrchestrator (Will layer) - orchestration only
- RemediationService (Body layer) - execution only
- This file: Thin wrapper for backward compatibility

DEPRECATION NOTICE:
This wrapper maintains backward compatibility while codebase migrates.
New code should use:
- will.orchestration.remediation_orchestrator.RemediationOrchestrator
- body.governance.remediation_service.RemediationService

This file will be removed in a future version once all imports are updated.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from shared.logger import getLogger
from will.orchestration.remediation_orchestrator import (
    AuditReport,
    RemediationOrchestrator,
    Violation,
)


logger = getLogger(__name__)


# Re-export types for backward compatibility
__all__ = [
    "AuditReport",
    "ConstitutionalMonitor",
    "KnowledgeGraphBuilderProtocol",
    "RemediationResult",
    "Violation",
]


# ID: e6f558e7-0ce7-41c8-9612-82a0c2c3f0ab
class KnowledgeGraphBuilderProtocol(Protocol):
    """Protocol for knowledge graph builder dependency."""

    # ID: 0d483f8e-d7cd-45b9-9f9e-3758f1c8721e
    async def build_and_sync(self) -> None: ...


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
    BACKWARD COMPATIBILITY WRAPPER

    This class maintains the old API while delegating to the new
    constitutionally-compliant architecture.

    Constitutional Architecture:
    - Will layer: RemediationOrchestrator (orchestration)
    - Body layer: RemediationService (execution)
    - This wrapper: Maintains old API during migration

    DEPRECATED: Use RemediationOrchestrator directly from Will layer

    Migration Path:
        OLD:
            from mind.enforcement.constitutional_monitor import ConstitutionalMonitor
            monitor = ConstitutionalMonitor(repo_path)
            result = await monitor.remediate_missing_headers_async()

        NEW:
            from will.orchestration.remediation_orchestrator import RemediationOrchestrator
            orchestrator = RemediationOrchestrator(repo_path)
            result = await orchestrator.remediate_missing_headers_async()
    """

    def __init__(
        self,
        repo_path: Path | str,
        knowledge_builder: KnowledgeGraphBuilderProtocol | None = None,
    ):
        """
        Initialize constitutional monitor (compatibility wrapper).

        Args:
            repo_path: Root path of the repository
            knowledge_builder: Optional knowledge graph builder

        Note:
            This wrapper delegates all operations to the new architecture.
        """
        self.repo_path = Path(repo_path)
        self.knowledge_builder = knowledge_builder

        # CONSTITUTIONAL FIX: Delegate to Will layer orchestrator
        self._orchestrator = RemediationOrchestrator(repo_path, knowledge_builder)

        logger.warning(
            "ConstitutionalMonitor is deprecated. "
            "Use will.orchestration.remediation_orchestrator.RemediationOrchestrator instead."
        )

    # ID: dae8dd95-0ac1-4a96-8ef8-92a4326499b1
    def audit_headers(self) -> AuditReport:
        """
        Audit all Python files for header compliance.

        DEPRECATED: Use RemediationOrchestrator.audit_headers() directly

        Returns:
            AuditReport with violations found
        """
        # Delegate to Will layer
        return self._orchestrator.audit_headers()

    # ID: c1f4ea23-8f5d-4c9a-b2d7-9e3a5c8f6d1b
    async def remediate_missing_headers_async(self) -> RemediationResult:
        """
        Remediate all files with missing headers.

        DEPRECATED: Use RemediationOrchestrator.remediate_missing_headers_async() directly

        Returns:
            RemediationResult with execution results
        """
        # Delegate to Will layer
        return await self._orchestrator.remediate_missing_headers_async()

    # ID: e7b2c4f9-3a1d-4e5b-8c9f-2a6d7e3b4c5f
    async def remediate_single_file_async(self, file_path: str) -> bool:
        """
        Remediate a single file.

        DEPRECATED: Use RemediationOrchestrator.remediate_single_file_async() directly

        Args:
            file_path: Path to file to remediate

        Returns:
            True if remediation succeeded, False otherwise
        """
        # Delegate to Will layer
        return await self._orchestrator.remediate_single_file_async(file_path)

    # ID: a3d5e7f9-1b2c-4d6e-8a9f-3b5c7d9e1f2a
    def validate_remediation(self, file_path: str) -> bool:
        """
        Validate that remediation was successful for a file.

        DEPRECATED: Use RemediationOrchestrator.validate_remediation() directly

        Args:
            file_path: Path to file to validate

        Returns:
            True if file is compliant, False otherwise
        """
        # Delegate to Will layer
        return self._orchestrator.validate_remediation(file_path)


# Factory function for backward compatibility
# ID: get-constitutional-monitor
# ID: b4c6d8e0-2a3b-4c5d-6e7f-8a9b0c1d2e3f
def get_constitutional_monitor(
    repo_path: Path | str | None = None,
    knowledge_builder: KnowledgeGraphBuilderProtocol | None = None,
) -> ConstitutionalMonitor:
    """
    Get ConstitutionalMonitor instance (compatibility wrapper).

    DEPRECATED: Use get_remediation_orchestrator() from Will layer instead

    Migration Path:
        OLD:
            from mind.enforcement.constitutional_monitor import get_constitutional_monitor
            monitor = get_constitutional_monitor()

        NEW:
            from will.orchestration.remediation_orchestrator import get_remediation_orchestrator
            orchestrator = get_remediation_orchestrator()

    Args:
        repo_path: Optional repository path
        knowledge_builder: Optional knowledge graph builder

    Returns:
        ConstitutionalMonitor wrapper instance
    """
    if repo_path is None:
        repo_path = Path.cwd()

    logger.warning(
        "get_constitutional_monitor() is deprecated. "
        "Use will.orchestration.remediation_orchestrator.get_remediation_orchestrator() instead."
    )

    return ConstitutionalMonitor(repo_path, knowledge_builder)
