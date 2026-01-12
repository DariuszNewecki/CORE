# src/features/self_healing/modularity_remediation_service.py
# ID: features.self_healing.modularity_remediation

"""
Service for automated architectural modularization.
Translates Modularity Score violations into executable A3 goals.

CONSTITUTIONAL FIX:
- Propagates 'write' intent to Autonomous Developer.
- Hardens the AI goal prompt to prevent path-as-code (math) hallucinations.
- FIXED: Replaced direct 'get_session' import with 'service_registry.session'
  to satisfy logic.di.no_global_session.
- ADDED: Logic Conservation Gate to prevent "Refactoring by Deletion".
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from body.services.service_registry import service_registry
from features.autonomy.autonomous_developer import develop_from_goal
from mind.logic.engines.ast_gate.checks.modularity_checks import ModularityChecker
from shared.config import settings
from shared.context import CoreContext
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: modularity_remediation_service
# ID: 122a3749-facf-4734-85e7-59b82dc61057
class ModularityRemediationService:
    """
    Closed-loop remediation:
    1. Measure Score -> 2. Generate Goal -> 3. A3 Develop -> 4. Verify Improvement
    """

    def __init__(self, context: CoreContext):
        self.context = context
        self.checker = ModularityChecker()

    # ID: 1d090cab-0cd5-4bc3-b9a8-5f8f6023b78c
    async def remediate_batch(
        self, min_score: float = 60.0, limit: int = 5, write: bool = False
    ) -> list[dict[str, Any]]:
        """Finds top offenders and heals them sequentially."""
        results = []

        # 1. Get the "Hit List"
        candidates = []
        skip_dirs = {
            ".venv",
            "venv",
            ".git",
            "work",
            "var",
            "__pycache__",
            ".pytest_cache",
        }

        for file in settings.REPO_PATH.rglob("*.py"):
            if any(skip_dir in file.parts for skip_dir in skip_dirs):
                continue

            rel_path = file.relative_to(settings.REPO_PATH)
            if not str(rel_path).startswith("src/"):
                continue

            findings = self.checker.check_refactor_score(
                file, {"max_score": min_score - 0.01}
            )
            if findings:
                candidates.append((file, findings[0]["details"]))

        candidates.sort(key=lambda x: x[1]["total_score"], reverse=True)
        to_process = candidates[:limit]

        logger.info(
            "🛠️ Modularity Healing Batch: %d files [Write: %s]", len(to_process), write
        )

        for file_path, details in to_process:
            res = await self.remediate_file(file_path, details, write=write)
            results.append(res)

        return results

    # ID: 325347d3-d68b-4e61-bd5b-04fee6fc6bef
    async def remediate_file(self, file_path: Path, details: dict, write: bool) -> dict:
        """Heals a single file using the A3 loop."""
        rel_path = str(file_path.relative_to(settings.REPO_PATH))
        start_score = details["total_score"]

        # Measure original logic size (characters)
        original_size = len(file_path.read_text(encoding="utf-8"))

        # CONSTITUTIONAL FIX: Hardened prompt prevents "Math Header" AND "Logic Evaporation"
        auto_goal = (
            f"Modularize {rel_path} to resolve architectural violations.\n"
            f"IDENTIFIED RESPONSIBILITIES: {', '.join(details['responsibilities'])}\n"
            f"CURRENT REFACTOR SCORE: {start_score:.1f}\n\n"
            f"CRITICAL CONSTITUTIONAL INSTRUCTIONS:\n"
            f"1. YOU MUST MIGRATE 100% OF THE EXISTING LOGIC. Truncation is a violation.\n"
            f"2. EVERY file you create MUST start with a comment header: # path/to/file.py\n"
            f"3. DO NOT write the path as code (e.g., avoid 'src / features').\n"
            f"4. All public symbols must have # ID: <uuid> tags.\n"
            f"5. The total logic volume of the new files must match or exceed the original."
        )

        logger.info(
            "🚀 Initiating A3 Healing for %s (Score: %.1f)...", rel_path, start_score
        )

        # 3. Trigger A3 Developer
        async with service_registry.session() as session:
            # We use 'crate' mode even in direct mode to inspect the result before success
            success, action_res = await develop_from_goal(
                session=session,
                context=self.context,
                goal=auto_goal,
                output_mode="crate",
                write=write,
            )

        # 4. LOGIC CONSERVATION GATE
        if success and isinstance(action_res, dict):
            new_files = action_res.get("files", {})
            total_new_size = sum(len(content) for content in new_files.values())

            # If the new logic is less than 40% of the original size, it's a "Lazy Failure"
            if total_new_size < (original_size * 0.4):
                logger.error(
                    "❌ REJECTED: Logic Evaporation Detected. New size (%d) is too small vs original (%d).",
                    total_new_size,
                    original_size,
                )
                success = False
                message = "Automated logic conservation check failed: Result too small."
            else:
                message = "Logic conservation verified."

        # 5. Verify Improvement (Only if it was a real write and passed the gate)
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
            "message": message if not success else "Success",
        }
