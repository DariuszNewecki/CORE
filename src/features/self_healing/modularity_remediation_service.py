# src/features/self_healing/modularity_remediation_service.py
# ID: 122a3749-facf-4734-85e7-59b82dc61057
"""Constitutional modularity remediation service.

PURIFIED (V2.7.4)
- Removed direct 'settings' import to satisfy architecture.boundary.settings_access.
- Uses repo_path from CoreContext for constitutional artifact loading.

Closed-loop remediation:
1. Measure Score → 2. Generate Goal → 3. Execute Workflow → 4. Verify Improvement
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from features.autonomy.autonomous_developer import develop_from_goal
from mind.governance.enforcement_loader import EnforcementMappingLoader
from mind.logic.engines.ast_gate.checks.modularity_checks import ModularityChecker
from shared.context import CoreContext
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: e3dbdef6-d998-4e23-b2e0-708eea5f6506
class ModularityRemediationService:
    """Constitutional modularity remediation service.

    Performs closed-loop remediation based on modularity score violations.
    """

    def __init__(self, context: CoreContext):
        """Initialize modularity remediation service."""
        self.context = context
        self.checker = ModularityChecker()

        # Constitutional fix: use repo_path from context instead of global settings
        repo_root = self.context.git_service.repo_path
        self.loader = EnforcementMappingLoader(repo_root / ".intent")

        mappings = self.loader.load_all_mappings()
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

        repo_root = self.context.git_service.repo_path
        src_root = repo_root / "src"
        if not src_root.exists():
            return []

        files: list[Path] = []
        for file in src_root.rglob("*.py"):
            if any(part in file.parts for part in skip_dirs):
                continue
            files.append(file)

        return files

    # ID: 74b0bdc4-dcfe-46ac-904d-6a1f0e585a43
    async def remediate_batch(
        self,
        min_score: float | None = None,
        limit: int = 5,
        write: bool = False,
    ) -> list[dict[str, Any]]:
        """Find and remediate files exceeding modularity threshold."""
        threshold = min_score or self.threshold
        logger.info("Starting modularity remediation (threshold=%.1f)", threshold)

        source_files = self._get_source_files()
        logger.info("Scanning %d files for modularity violations...", len(source_files))

        violators: list[dict[str, Any]] = []

        for file_path in source_files:
            try:
                findings = self.checker.check_refactor_score(
                    file_path,
                    {"max_score": threshold},
                )

                if findings:
                    for finding in findings:
                        details = finding.get("details", {})
                        score = details.get("total_score", 0)
                        if score >= threshold:
                            violators.append(
                                {
                                    "file": file_path,
                                    "score": score,
                                    "details": details,
                                }
                            )

            except Exception as e:
                logger.debug("Could not check %s: %s", file_path, e)
                continue

        if not violators:
            logger.info("No modularity violations found")
            return []

        violators.sort(key=lambda x: x["score"], reverse=True)
        violators = violators[:limit]

        results: list[dict[str, Any]] = []
        repo_root = self.context.git_service.repo_path

        for violator in violators:
            file_path = violator["file"]
            score = violator["score"]

            logger.info("Remediating %s (score=%.1f)", file_path.name, score)

            goal = (
                f"Refactor {file_path.relative_to(repo_root)} "
                f"to reduce modularity score from {score:.1f} to below {threshold:.1f}. "
                "Split responsibilities, extract helpers, improve cohesion."
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
                        "file": str(file_path.relative_to(repo_root)),
                        "original_score": score,
                        "success": success,
                        "message": message,
                    }
                )

            except Exception as e:
                logger.error("Remediation failed for %s: %s", file_path, e)
                results.append(
                    {
                        "file": str(file_path.relative_to(repo_root)),
                        "original_score": score,
                        "success": False,
                        "message": str(e),
                    }
                )

        return results
