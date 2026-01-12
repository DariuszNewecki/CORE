# src/features/self_healing/modularity_remediation_service.py
# ID: features.self_healing.modularity_remediation

"""
Service for automated architectural modularization.
Translates Modularity Score violations into executable A3 goals.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from features.autonomy.autonomous_developer import develop_from_goal
from mind.logic.engines.ast_gate.checks.modularity_checks import ModularityChecker
from shared.config import settings
from shared.context import CoreContext
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: modularity_remediation_service
# ID: 07995697-3482-44bd-a305-f083e98e761f
class ModularityRemediationService:
    """
    Closed-loop remediation:
    1. Measure Score -> 2. Generate Goal -> 3. A3 Develop -> 4. Verify Improvement
    """

    def __init__(self, context: CoreContext):
        self.context = context
        self.checker = ModularityChecker()

    # ID: 38dbe38e-0eb3-43ce-883d-b7f72383fd07
    async def remediate_batch(
        self, min_score: float = 60.0, limit: int = 5, write: bool = False
    ) -> list[dict[str, Any]]:
        """Finds top offenders and heals them sequentially."""
        results = []

        # 1. Get the "Hit List" (identical logic to refactor suggest)
        candidates = []
        for file in settings.REPO_PATH.rglob("*.py"):
            if any(x in file.parts for x in [".venv", "venv", ".git", "work", "var"]):
                continue
            if not str(file.relative_to(settings.REPO_PATH)).startswith("src/"):
                continue

            findings = self.checker.check_refactor_score(
                file, {"max_score": min_score - 0.01}
            )
            if findings:
                candidates.append((file, findings[0]["details"]))

        # Sort by score descending
        candidates.sort(key=lambda x: x[1]["total_score"], reverse=True)
        to_process = candidates[:limit]

        logger.info("🛠️ Batch Modularity Healing: Processing %d files", len(to_process))

        for file_path, details in to_process:
            res = await self.remediate_file(file_path, details, write=write)
            results.append(res)

        return results

    # ID: 61f9c91e-db11-4718-a255-67e813c7164e
    async def remediate_file(self, file_path: Path, details: dict, write: bool) -> dict:
        """Heals a single file using the A3 loop."""
        rel_path = str(file_path.relative_to(settings.REPO_PATH))
        start_score = details["total_score"]

        # 2. Synthesize Goal (The Zero-Prompt Logic)
        auto_goal = (
            f"Modularize {rel_path} to resolve architectural violations.\n"
            f"IDENTIFIED RESPONSIBILITIES: {', '.join(details['responsibilities'])}\n"
            f"CURRENT SEMANTIC COHESION: {details['cohesion']:.2f} (Target: > 0.70)\n"
            f"CURRENT REFACTOR SCORE: {start_score:.1f} (Target: < 60.0)\n\n"
            f"INSTRUCTION: Extract logic into smaller, cohesive modules. "
            f"Ensure the original {rel_path} becomes a thin orchestrator or is split entirely."
        )

        logger.info("🚀 Healing %s (Score: %.1f)...", rel_path, start_score)

        # 3. Trigger A3 Developer
        async with get_session() as session:
            success, message = await develop_from_goal(
                session=session,
                context=self.context,
                goal=auto_goal,
                output_mode="direct",  # A3 will apply changes via ActionExecutor
            )

        # 4. Verify Improvement
        final_score = start_score
        if success and write:
            post_findings = self.checker.check_refactor_score(
                file_path, {"max_score": 0}
            )
            if post_findings:
                final_score = post_findings[0]["details"]["total_score"]

        improvement = start_score - final_score

        return {
            "file": rel_path,
            "success": success,
            "start_score": start_score,
            "final_score": final_score,
            "improvement": improvement,
            "message": message,
        }
