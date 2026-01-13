# src/features/self_healing/modularity_remediation_service.py
# ID: features.self_healing.modularity_remediation

"""
Service for automated architectural modularization.
Translates Modularity Score violations into executable A3 goals.

This service acts as the 'General Contractor' for modularity health.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from body.services.service_registry import service_registry
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
    Closed-loop remediation:
    1. Measure Score -> 2. Generate Goal -> 3. A3 Develop -> 4. Verify Improvement
    """

    def __init__(self, context: CoreContext):
        self.context = context
        self.checker = ModularityChecker()

    def _get_constitutional_threshold(self) -> float:
        """Retrieves the authoritative 'max_score' from the .intent YAML."""
        try:
            loader = EnforcementMappingLoader(settings.REPO_PATH / ".intent")
            strategy = loader.get_enforcement_strategy(
                "modularity.refactor_score_threshold"
            )
            if strategy and "params" in strategy:
                return float(strategy["params"].get("max_score", 60.0))
        except Exception:
            pass
        return 60.0

    # ID: 1d090cab-0cd5-4bc3-b9a8-5f8f6023b78c
    async def remediate_batch(
        self, min_score: float | None = None, limit: int = 5, write: bool = False
    ) -> list[dict[str, Any]]:
        """Finds top offenders and heals them sequentially."""
        results = []

        # Use the YAML threshold if the user didn't provide a specific score
        target_threshold = (
            min_score if min_score is not None else self._get_constitutional_threshold()
        )

        # 1. Gather candidates (The "Hit List")
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

        # Scan production code only
        src_root = settings.REPO_PATH / "src"
        for file in src_root.rglob("*.py"):
            if any(skip_dir in file.parts for skip_dir in skip_dirs):
                continue

            # We use the new logic engine to find files above the threshold
            findings = self.checker.check_refactor_score(
                file, {"max_score": target_threshold}
            )
            if findings:
                candidates.append((file, findings[0]["details"]))

        # Sort by worst score first
        candidates.sort(key=lambda x: x[1]["total_score"], reverse=True)
        to_process = candidates[:limit]

        logger.info(
            "🛠️ Modularity Healing Batch: %d files [Write: %s, Threshold: %s]",
            len(to_process),
            write,
            target_threshold,
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
        original_size = len(file_path.read_text(encoding="utf-8"))

        # CONSTITUTIONAL FIX: Precision-engineered AI goal
        auto_goal = (
            f"Modularize {rel_path} to resolve architectural violations.\n"
            f"CURRENT MODULARITY DEBT: {start_score:.1f}/100\n"
            f"IDENTIFIED RESPONSIBILITIES: {', '.join(details['responsibilities'])}\n\n"
            f"CRITICAL CONSTITUTIONAL INSTRUCTIONS:\n"
            f"1. LOGIC CONSERVATION: You must migrate 100% of the existing logic. Truncation is forbidden.\n"
            f"2. HEADERS: Every file you create MUST start with a comment header like: # path/to/file.py\n"
            f"3. IDENTITY: All public symbols must have # ID: <uuid> tags.\n"
            f"4. MATHEMATICAL IMPROVEMENT: The goal is to reduce the debt score by splitting the code into smaller, more cohesive modules."
        )

        logger.info(
            "🚀 Initiating A3 Healing for %s (Initial Score: %.1f)...",
            rel_path,
            start_score,
        )

        # 3. Trigger A3 Developer (Planning -> Specification -> Execution)
        async with service_registry.session() as session:
            success, action_res = await develop_from_goal(
                session=session,
                context=self.context,
                goal=auto_goal,
                output_mode="crate",
                write=write,
            )

        message = "Autonomous process completed."

        # 4. LOGIC CONSERVATION GATE (The "Anti-Hallucination" Guard)
        if success and isinstance(action_res, dict):
            new_files = action_res.get("files", {})
            total_new_size = sum(len(content) for content in new_files.values())

            # If the new code is suspiciously small, the AI likely "cheated" by deleting logic
            if total_new_size < (original_size * 0.4):
                logger.error(
                    "❌ REJECTED: Logic Evaporation Detected. New size (%d chars) vs original (%d chars).",
                    total_new_size,
                    original_size,
                )
                success = False
                message = "REJECTED: Result too small (Logic Evaporation)."
            else:
                logger.info(
                    "✅ Logic conservation verified (Size: %d chars).", total_new_size
                )

        # 5. Verify Improvement (Final Audit)
        final_score = start_score
        if success and write:
            # Re-run the checker on the file to see if the score actually went down
            post_findings = self.checker.check_refactor_score(
                file_path, {"max_score": 0}
            )
            if post_findings:
                final_score = post_findings[0]["details"]["total_score"]
                improvement = start_score - final_score
                logger.info(
                    "📈 Modularity Improvement: %.1f points removed.", improvement
                )

        return {
            "file": rel_path,
            "success": success,
            "start_score": start_score,
            "final_score": final_score,
            "improvement": start_score - final_score,
            "message": (
                message if not success else "✅ Refactoring successfully applied."
            ),
        }
