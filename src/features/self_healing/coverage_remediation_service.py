# src/features/self_healing/coverage_remediation_service.py

"""
Enhanced coverage remediation service with configurable generator selection.

This service routes to either the original or enhanced test generator
based on configuration, allowing gradual rollout and A/B testing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mind.governance.audit_context import AuditorContext
from shared.logger import getLogger
from will.orchestration.cognitive_service import CognitiveService

from features.self_healing.full_project_remediation import FullProjectRemediationService
from src.features.self_healing.single_file_remediation import (
    EnhancedSingleFileRemediationService,
)

logger = getLogger(__name__)


# ID: 9aa0a5f2-ca66-41dc-9d54-f7815cea3bbd
async def remediate_coverage_enhanced(
    cognitive_service: CognitiveService,
    auditor_context: AuditorContext,
    target_coverage: int | None = None,
    file_path: Path | None = None,
    use_enhanced: bool = True,
    max_complexity: str = "MODERATE",
) -> dict[str, Any]:
    """
    Enhanced coverage remediation with rich context analysis.

    Args:
        cognitive_service: AI service for code generation
        auditor_context: Constitutional audit context
        target_coverage: Optional target coverage percentage (default: 75)
        file_path: Optional specific file to remediate (single-file mode)
        use_enhanced: Whether to use enhanced generator (default: True)
        max_complexity: Maximum complexity to attempt (SIMPLE/MODERATE/COMPLEX)

    Returns:
        Remediation results and metrics
    """
    if file_path:
        logger.info(f"Starting enhanced single-file remediation for {file_path}")
        if use_enhanced:
            service = EnhancedSingleFileRemediationService(
                cognitive_service, auditor_context, file_path, max_complexity
            )
            logger.info(
                f"Using EnhancedTestGenerator (max_complexity={max_complexity})"
            )
        else:
            from features.self_healing.single_file_remediation import (
                SingleFileRemediationService,
            )

            service = SingleFileRemediationService(
                cognitive_service, auditor_context, file_path
            )
            logger.info("Using original TestGenerator")
        return await service.remediate()
    else:
        logger.info("Starting full-project remediation (using original implementation)")
        service = FullProjectRemediationService(cognitive_service, auditor_context)
        if target_coverage is not None:
            service.config["minimum_threshold"] = target_coverage
        return await service.remediate()


# ID: 1b2d54bb-0ef0-40e0-b41f-5101d8c16be0
async def remediate_coverage(
    cognitive_service: CognitiveService,
    auditor_context: AuditorContext,
    target_coverage: int | None = None,
    file_path: Path | None = None,
    max_complexity: str = "MODERATE",
) -> dict[str, Any]:
    """
    Default remediation function - now uses enhanced generator.

    This maintains backward compatibility while defaulting to the improved version.
    """
    return await remediate_coverage_enhanced(
        cognitive_service=cognitive_service,
        auditor_context=auditor_context,
        target_coverage=target_coverage,
        file_path=file_path,
        use_enhanced=True,
        max_complexity=max_complexity,
    )
