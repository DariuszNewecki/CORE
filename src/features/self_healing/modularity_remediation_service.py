# src/features/self_healing/modularity_remediation_service.py
# ID: features.self_healing.modularity_remediation

"""
Modularity Remediation Service - Constitutional Workflow Edition

Service for automated architectural modularization using explicit workflow orchestration.

Uses 'refactor_modularity' workflow which:
1. Plans refactoring strategy
2. Generates refactored code
3. Validates with canary (existing tests)
4. Checks style
5. Applies changes

Does NOT generate tests - that's coverage_remediation's job.

This service acts as the 'General Contractor' for modularity health.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from features.autonomy.autonomous_developer import develop_from_goal
from mind.governance.enforcement_loader import EnforcementMappingLoader
from mind.logic.engines.ast_gate.checks.modularity_checks import ModularityChecker
from shared.config import settings
from shared.context import CoreContext
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: modularity_remediation_service
# ID: 122a3749-facf-4734-85e7-59b82dc61057
class ModularityRemediationService:
    """
    Constitutional modularity remediation.

    Closed-loop remediation:
    1. Measure Score → 2. Generate Goal → 3. Execute Workflow → 4. Verify Improvement

    Uses explicit 'refactor_modularity' workflow type for constitutional governance.
    """

    def __init__(self, context: CoreContext):
        """
        Initialize modularity remediation service.

        Args:
            context: CoreContext with constitutional capabilities
        """
        self.context = context
        self.checker = ModularityChecker()
        self.loader = EnforcementMappingLoader(settings.REPO_PATH / ".intent")

        # Load constitutional threshold
        mappings = self.loader.load()
        self.threshold = self._get_constitutional_threshold(mappings)

    def _get_constitutional_threshold(self, mappings: dict[str, Any]) -> float:
        """
        Extract max_score threshold from constitutional enforcement mappings.

        Args:
            mappings: Enforcement mappings from .intent/

        Returns:
            Constitutional threshold for modularity score (default: 60.0)
        """
        try:
            for rule_id, mapping in mappings.items():
                if "modularity" in rule_id.lower():
                    params = mapping.get("parameters", {})
                    if "max_score" in params:
                        return float(params["max_score"])
        except Exception as e:
            logger.warning("Could not load constitutional threshold: %s", e)

        return 60.0  # Constitutional default

    # ID: 74b0bdc4-dcfe-46ac-904d-6a1f0e585a43
    async def remediate_batch(
        self, min_score: float | None = None, limit: int = 5, write: bool = False
    ) -> list[dict[str, Any]]:
        """
        Find and remediate files exceeding modularity threshold.

        Args:
            min_score: Override constitutional threshold (for testing)
            limit: Maximum files to process in one batch
            write: Whether to apply changes

        Returns:
            List of remediation results
        """
        threshold = min_score if min_score is not None else self.threshold

        logger.info(
            "🔍 Scanning for files exceeding modularity threshold: %.1f", threshold
        )

        # Find violating files
        findings = self.checker.check_all_files({"max_score": threshold})

        if not findings:
            logger.info("✅ No files exceed the modularity threshold")
            return []

        # Sort by score (worst first) and limit
        findings.sort(key=lambda f: f["details"]["total_score"], reverse=True)
        findings = findings[:limit]

        logger.info(
            "📋 Found %d files to remediate (processing %d)",
            len(findings),
            min(limit, len(findings)),
        )

        # Process each file
        results = []
        for finding in findings:
            result = await self._remediate_single_file(
                file_path=Path(finding["file"]),
                start_score=finding["details"]["total_score"],
                details=finding["details"],
                write=write,
            )
            results.append(result)

        return results

    async def _remediate_single_file(
        self,
        file_path: Path,
        start_score: float,
        details: dict[str, Any],
        write: bool,
    ) -> dict[str, Any]:
        """
        Remediate a single file using constitutional workflow.

        Args:
            file_path: Path to file to remediate
            start_score: Initial modularity score
            details: Detailed violation information
            write: Whether to apply changes

        Returns:
            Remediation result with success status and improvement metrics
        """
        relative_path = file_path.relative_to(settings.REPO_PATH)

        logger.info(
            "🔧 Remediating: %s (score: %.1f)",
            relative_path,
            start_score,
        )

        # Build goal for autonomous developer
        goal = (
            f"Refactor {relative_path} to improve modularity. "
            f"Current score: {start_score:.1f}. "
            f"Target: < 60.0. "
            f"Issues: {details.get('responsibility_count', 0)} responsibilities, "
            f"cohesion {details.get('cohesion', 0):.2f}"
        )

        # Execute using explicit refactor_modularity workflow
        success, message = await develop_from_goal(
            context=self.context,
            goal=goal,
            workflow_type="refactor_modularity",
            write=write,
        )

        # Measure improvement
        if success:
            findings = self.checker.check_refactor_score(
                file_path,
                {"max_score": 0},  # Get score regardless of threshold
            )
            final_score = (
                findings[0]["details"]["total_score"] if findings else start_score
            )
            improvement = start_score - final_score
        else:
            final_score = start_score
            improvement = 0.0

        return {
            "file": str(relative_path),
            "success": success,
            "start_score": start_score,
            "final_score": final_score,
            "improvement": improvement,
            "message": message,
        }
