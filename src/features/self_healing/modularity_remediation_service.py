# src/features/self_healing/modularity_remediation_service.py
"""
Constitutional modularity remediation service.

FIXED VERSION - Corrects API mismatches:
- EnforcementMappingLoader.load() -> load_all_mappings()
- ModularityChecker.check_all_files() -> check_refactor_score() per file
- Added proper file enumeration
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
    """

    def __init__(self, context: CoreContext):
        """Initialize modularity remediation service."""
        self.context = context
        self.checker = ModularityChecker()
        self.loader = EnforcementMappingLoader(settings.REPO_PATH / ".intent")

        # Load constitutional threshold
        mappings = self.loader.load_all_mappings()  # FIXED: was load()
        self.threshold = self._get_constitutional_threshold(mappings)

    def _get_constitutional_threshold(self, mappings: dict[str, Any]) -> float:
        """Extract max_score threshold from constitutional enforcement mappings."""
        try:
            for rule_id, mapping in mappings.items():
                if "modularity" in rule_id.lower():
                    params = mapping.get("parameters", {})
                    if "max_score" in params:
                        return float(params["max_score"])
        except Exception as e:
            logger.warning("Could not load constitutional threshold: %s", e)
        return 60.0  # Constitutional default

    def _get_source_files(self) -> list[Path]:
        """Enumerate source files, excluding test/temp directories."""
        skip_dirs = {
            ".venv",
            "venv",
            ".git",
            "work",
            "var",
            "__pycache__",
            ".pytest_cache",
            "tests",
            "migrations",
            "reports",
        }
        src_root = settings.REPO_PATH / "src"
        if not src_root.exists():
            return []

        files = []
        for file in src_root.rglob("*.py"):
            if any(part in file.parts for part in skip_dirs):
                continue
            files.append(file)
        return files

    # ID: 74b0bdc4-dcfe-46ac-904d-6a1f0e585a43
    async def remediate_batch(
        self, min_score: float | None = None, limit: int = 5, write: bool = False
    ) -> list[dict[str, Any]]:
        """
        Find and remediate files exceeding modularity threshold.

        Args:
            min_score: Minimum score to trigger remediation (uses threshold if None)
            limit: Max number of files to remediate
            write: Actually apply changes

        Returns:
            List of remediation results
        """
        threshold = min_score or self.threshold
        logger.info("Starting modularity remediation (threshold=%.1f)", threshold)

        # FIXED: Enumerate files and check each one
        source_files = self._get_source_files()
        logger.info("Scanning %d files for modularity violations...", len(source_files))

        # Find violators
        violators = []
        for file_path in source_files:
            try:
                # FIXED: Use check_refactor_score() per file, not check_all_files()
                findings = self.checker.check_refactor_score(
                    file_path, {"max_score": threshold}
                )
                if findings:
                    for finding in findings:
                        details = finding.get("details", {})
                        score = details.get("total_score", 0)
                        if score >= threshold:
                            violators.append(
                                {"file": file_path, "score": score, "details": details}
                            )
            except Exception as e:
                logger.debug("Could not check %s: %s", file_path, e)
                continue

        if not violators:
            logger.info("✅ No modularity violations found")
            return []

        # Sort by score (highest first) and limit
        violators.sort(key=lambda x: x["score"], reverse=True)
        violators = violators[:limit]

        logger.info(
            "Found %d violators, remediating top %d",
            len(violators),
            min(limit, len(violators)),
        )

        # Remediate each violator
        results = []
        for violator in violators:
            file_path = violator["file"]
            score = violator["score"]

            logger.info("Remediating %s (score=%.1f)", file_path.name, score)

            goal = (
                f"Refactor {file_path.relative_to(settings.REPO_PATH)} "
                f"to reduce modularity score from {score:.1f} to below {threshold:.1f}. "
                f"Split responsibilities, extract helpers, improve cohesion."
            )

            try:
                success, message = await develop_from_goal(
                    context=self.context,
                    goal=goal,
                    workflow_type="refactor_modularity",
                    write=write,
                )

                results.append(
                    {
                        "file": str(file_path.relative_to(settings.REPO_PATH)),
                        "original_score": score,
                        "success": success,
                        "message": message,
                    }
                )

            except Exception as e:
                logger.error("Remediation failed for %s: %s", file_path, e)
                results.append(
                    {
                        "file": str(file_path.relative_to(settings.REPO_PATH)),
                        "original_score": score,
                        "success": False,
                        "message": str(e),
                    }
                )

        return results


__all__ = ["ModularityRemediationService"]
