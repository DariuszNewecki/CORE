# src/will/self_healing/modularity_remediation_service.py
"""Constitutional modularity remediation service.

Closed-loop remediation:
1. Measure Score → 2. Generate Goal → 3. Execute Workflow → 4. Verify Improvement
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from body.validators.logic_conservation_validator import LogicConservationValidator
from mind.governance.enforcement_loader import EnforcementMappingLoader
from mind.logic.engines.ast_gate.checks.modularity_checks import ModularityChecker
from shared.context import CoreContext
from shared.logger import getLogger
from will.autonomy.autonomous_developer import develop_from_goal


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
        conservation_validator = LogicConservationValidator()

        for violator in violators:
            file_path = violator["file"]
            score = violator["score"]
            rel_path = str(file_path.relative_to(repo_root))

            logger.info("Remediating %s (score=%.1f)", file_path.name, score)

            # Snapshot original before the workflow writes anything.
            original_code = file_path.read_text(encoding="utf-8")

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

                # Logic Conservation Gate — mirrors ComplexityRemediationService._run_reflex_loop.
                # Only evaluated when write=True and the workflow reported success.
                # In dry-run mode ExecutionPhase never writes files, so there is nothing to measure.
                if success and write:
                    new_code = file_path.read_text(encoding="utf-8")
                    conservation_verdict = await conservation_validator.evaluate(
                        original_code=original_code,
                        proposed_map={rel_path: new_code},
                        deletions_authorized=False,
                    )
                    if not conservation_verdict.ok:
                        ratio = conservation_verdict.data.get("ratio", 0.0)
                        logger.error(
                            "Logic evaporation in %s (ratio=%.2f) — reverting.",
                            file_path.name,
                            ratio,
                        )
                        self.context.file_handler.write_runtime_text(
                            rel_path, original_code
                        )
                        success = False
                        message = (
                            f"Logic evaporation detected (ratio={ratio:.2f}); "
                            "refactor reverted."
                        )

                results.append(
                    {
                        "file": rel_path,
                        "original_score": score,
                        "success": success,
                        "message": message,
                    }
                )

            except Exception as e:
                logger.error("Remediation failed for %s: %s", file_path, e)
                results.append(
                    {
                        "file": rel_path,
                        "original_score": score,
                        "success": False,
                        "message": str(e),
                    }
                )

        return results
