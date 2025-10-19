# src/features/self_healing/coverage_remediation_service.py
"""
Facade for autonomous test generation - routes to single-file or full-project mode.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.cognitive_service import CognitiveService
from shared.logger import getLogger

from features.governance.audit_context import AuditorContext
from features.self_healing.full_project_remediation import FullProjectRemediationService
from features.self_healing.single_file_remediation import SingleFileRemediationService

log = getLogger(__name__)


# ID: 60211bee-618a-48df-b527-018e093f0868
async def remediate_coverage(
    cognitive_service: CognitiveService,
    auditor_context: AuditorContext,
    target_coverage: int | None = None,
    file_path: Path | None = None,
) -> dict[str, Any]:
    """
    Public interface for autonomous coverage remediation.

    Routes to either single-file or full-project remediation based on parameters.

    Args:
        cognitive_service: AI service for code generation
        auditor_context: Constitutional audit context
        target_coverage: Optional target coverage percentage (default: 75)
        file_path: Optional specific file to remediate (single-file mode)

    Returns:
        Remediation results and metrics
    """
    if file_path:
        service = SingleFileRemediationService(
            cognitive_service, auditor_context, file_path
        )
    else:
        service = FullProjectRemediationService(cognitive_service, auditor_context)
        if target_coverage is not None:
            service.config["minimum_threshold"] = target_coverage

    return await service.remediate()
