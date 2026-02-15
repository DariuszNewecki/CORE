# src/features/self_healing/coverage_remediation_service.py
# ID: 32606196-d12a-4480-9add-51b26f30ee22

"""
Enhanced coverage remediation service - V2 Adaptive Implementation.

Following the V2 Alignment Roadmap, this service now routes all requests
through the Enhanced/Adaptive generation path. The legacy monolithic
V1 FullProjectRemediationService has been removed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from body.self_healing.batch_remediation_service import BatchRemediationService
from body.self_healing.single_file_remediation import (
    EnhancedSingleFileRemediationService,
)
from mind.governance.audit_context import AuditorContext
from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger
from will.orchestration.cognitive_service import CognitiveService


logger = getLogger(__name__)


# ID: ce7c1db5-ef5b-4f70-9379-b5010b89e08d
async def remediate_coverage_enhanced(
    cognitive_service: CognitiveService,
    auditor_context: AuditorContext,
    file_handler: FileHandler,
    repo_root: Path,
    target_coverage: int | None = None,
    file_path: Path | None = None,
    max_complexity: str = "MODERATE",
) -> dict[str, Any]:
    """
    Enhanced coverage remediation with rich context analysis.

    If a specific file is provided, it uses surgical remediation.
    Otherwise, it uses the BatchRemediationService to heal the project
    prioritizing the lowest coverage areas.
    """
    if file_path:
        logger.info("Starting V2 single-file remediation for: %s", file_path)
        service = EnhancedSingleFileRemediationService(
            cognitive_service=cognitive_service,
            auditor_context=auditor_context,
            file_path=file_path,
            file_handler=file_handler,
            repo_root=repo_root,
            max_complexity=max_complexity,
        )
        return await service.remediate()

    # V2 ALIGNMENT: Project-wide remediation now uses the Batch (prioritized) path
    logger.info("Starting V2 batch remediation (Target: %s%%)", target_coverage or 75)
    batch_service = BatchRemediationService(
        cognitive_service=cognitive_service,
        auditor_context=auditor_context,
        max_complexity=max_complexity,
    )

    # We attempt to heal a batch of files (defaulting to 5 at a time for safety)
    return await batch_service.process_batch(count=5)


async def _remediate_coverage(
    cognitive_service: CognitiveService,
    auditor_context: AuditorContext,
    file_handler: FileHandler,
    repo_root: Path,
    target_coverage: int | None = None,
    file_path: Path | None = None,
    max_complexity: str = "MODERATE",
) -> dict[str, Any]:
    """
    Authoritative internal entry point for coverage remediation.
    Maintained for background watchers (e.g. coverage_watcher.py).
    """
    return await remediate_coverage_enhanced(
        cognitive_service=cognitive_service,
        auditor_context=auditor_context,
        file_handler=file_handler,
        repo_root=repo_root,
        target_coverage=target_coverage,
        file_path=file_path,
        max_complexity=max_complexity,
    )


# Alias for external consumers
remediate_coverage = _remediate_coverage
