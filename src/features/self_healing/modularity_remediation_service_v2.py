# src/features/self_healing/modularity_remediation_service_v2.py
# ID: features.self_healing.modularity_remediation_v2

"""
Modularity Remediation Service V2 - Constitutional Workflow Edition

Uses explicit 'refactor_modularity' workflow which:
1. Plans refactoring strategy
2. Generates refactored code
3. Validates with canary (existing tests)
4. Checks style
5. Applies changes

Does NOT generate tests - that's coverage_remediation's job.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from features.autonomy.autonomous_developer_v2 import develop_from_goal_v2
from mind.governance.enforcement_loader import EnforcementMappingLoader
from mind.logic.engines.ast_gate.checks.modularity_checks import ModularityChecker
from shared.config import settings
from shared.context import CoreContext
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 6f7g8h9i-0j1k-2l3m-4n5o-6p7q8r9s0t1u
# ID: b1a64e3c-0871-45a0-baae-c9967f28b183
class ModularityRemediationServiceV2:
    """
    Constitutional modularity remediation.

    Workflow: refactor_modularity (no test generation)
    """

    def __init__(self, context: CoreContext):
        self.context = context
        self.checker = ModularityChecker()

    def _get_constitutional_threshold(self) -> float:
        """Load threshold from .intent/enforcement/"""
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

    # ID: 827c3f95-cef1-4225-ba6e-9b8c8c38da10
    async def remediate_batch(
        self, min_score: float | None = None, limit: int = 5, write: bool = False
    ) -> list[dict[str, Any]]:
        """Find and fix top modularity offenders"""
        results = []

        target_threshold = (
            min_score if min_score is not None else self._get_constitutional_threshold()
        )

        # Find candidates
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

        src_root = settings.REPO_PATH / "src"
        for file in src_root.rglob("*.py"):
            if any(skip_dir in file.parts for skip_dir in skip_dirs):
                continue

            findings = self.checker.check_refactor_score(
                file, {"max_score": target_threshold}
            )
            if findings:
                candidates.append((file, findings[0]["details"]))

        # Sort by worst score
        candidates.sort(key=lambda x: x[1]["total_score"], reverse=True)
        to_process = candidates[:limit]

        logger.info(
            "🛠️  Modularity Remediation V2: %d files [Write: %s, Threshold: %.1f]",
            len(to_process),
            write,
            target_threshold,
        )

        # Process each file
        for file_path, details in to_process:
            res = await self.remediate_file(file_path, details, write=write)
            results.append(res)

        return results

    # ID: a5564dca-4768-445e-9722-1a35d0c3fd1c
    async def remediate_file(self, file_path: Path, details: dict, write: bool) -> dict:
        """Remediate a single file using refactor_modularity workflow"""
        start_score = details["total_score"]
        relative_path = file_path.relative_to(settings.REPO_PATH)

        logger.info("📝 Remediating: %s (score: %.1f)", relative_path, start_score)

        # Build goal for the workflow
        goal = (
            f"Refactor {relative_path} to improve modularity. "
            f"Current score: {start_score:.1f}. "
            f"Target: < 60.0. "
            f"Issues: {details.get('responsibility_count', 0)} responsibilities, "
            f"cohesion {details.get('cohesion', 0):.2f}"
        )

        # Execute using refactor_modularity workflow
        # This workflow does NOT generate tests
        success, message = await develop_from_goal_v2(
            context=self.context,
            goal=goal,
            workflow_type="refactor_modularity",  # ← Explicit workflow
            write=write,
        )

        # Measure improvement
        if success:
            findings = self.checker.check_refactor_score(
                file_path,
                {"max_score": 0},  # Get score regardless
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
