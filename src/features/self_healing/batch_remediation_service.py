# src/features/self_healing/batch_remediation_service.py

"""
Batch test generation service for processing multiple files efficiently.

Selects files by lowest coverage and complexity threshold, processes them
in order, and provides progress reporting.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mind.governance.audit_context import AuditorContext
from shared.config import settings
from shared.logger import getLogger
from will.orchestration.cognitive_service import CognitiveService

from features.self_healing.coverage_analyzer import CoverageAnalyzer
from features.self_healing.single_file_remediation import (
    EnhancedSingleFileRemediationService,
)

logger = getLogger(__name__)


# ID: 6d9e1303-f11b-41c0-8897-d5016854a74d
class BatchRemediationService:
    """
    Processes multiple files for test generation in a single run.

    Strategy:
    1. Get all files with coverage data
    2. Filter by complexity threshold
    3. Sort by lowest coverage first (biggest wins)
    4. Process up to N files
    5. Report results
    """

    def __init__(
        self,
        cognitive_service: CognitiveService,
        auditor_context: AuditorContext,
        max_complexity: str = "MODERATE",
    ):
        from features.self_healing.complexity_filter import ComplexityFilter

        self.cognitive = cognitive_service
        self.auditor = auditor_context
        self.max_complexity = max_complexity
        self.analyzer = CoverageAnalyzer()
        self.complexity_filter = ComplexityFilter(max_complexity=max_complexity)

    # ID: 1b9a6db1-2cca-4410-b232-79edbd3d9809
    async def process_batch(self, count: int) -> dict[str, Any]:
        """
        Process N files for test generation.

        Args:
            count: Number of files to process

        Returns:
            Batch results with summary
        """
        logger.info("Batch Remediation: Finding candidate files...")
        candidates = self._get_candidate_files()

        if not candidates:
            logger.warning("No suitable files found for testing")
            return {"status": "no_candidates", "processed": 0, "results": []}

        logger.info(
            "Found %d files below 75%% coverage. Filtering by complexity: %s",
            len(candidates),
            self.max_complexity,
        )

        filtered = self._filter_by_complexity(candidates)
        if not filtered:
            logger.warning(
                "No files match complexity threshold: %s", self.max_complexity
            )
            return {"status": "no_matches", "processed": 0, "results": []}

        logger.info("%d files match complexity threshold", len(filtered))

        to_process = filtered[:count]
        logger.info("Processing %d files", len(to_process))

        results = []
        for i, (file_path, coverage) in enumerate(to_process, 1):
            logger.info(
                "Processing file %d/%d: %s (%.1f%% coverage)",
                i,
                len(to_process),
                file_path,
                coverage,
            )

            result = await self._process_file(file_path)
            results.append(
                {"file": str(file_path), "original_coverage": coverage, **result}
            )

        self._log_summary(results)
        return {"status": "completed", "processed": len(results), "results": results}

    def _get_candidate_files(self) -> list[tuple[Path, float]]:
        """Get files with coverage data, sorted by lowest coverage first."""
        coverage_data = self.analyzer.get_module_coverage()
        if not coverage_data:
            return []
        candidates = [
            (settings.REPO_PATH / path, percent)
            for path, percent in coverage_data.items()
            if path.startswith("src/") and percent < 75.0
        ]
        candidates.sort(key=lambda x: x[1])
        return candidates

    def _filter_by_complexity(
        self, candidates: list[tuple[Path, float]]
    ) -> list[tuple[Path, float]]:
        """Filter candidates by complexity threshold."""
        filtered = []
        for file_path, coverage in candidates:
            if not file_path.exists():
                continue
            complexity_check = self.complexity_filter.should_attempt(file_path)
            if complexity_check["should_attempt"]:
                filtered.append((file_path, coverage))
                logger.debug("Accepted %s: {complexity_check['reason']}", file_path)
            else:
                logger.debug("Filtered %s: {complexity_check['reason']}", file_path)
        return filtered

    async def _process_file(self, file_path: Path) -> dict[str, Any]:
        """Process a single file."""
        try:
            service = EnhancedSingleFileRemediationService(
                self.cognitive,
                self.auditor,
                file_path,
                max_complexity=self.max_complexity,
            )
            result = await service.remediate()
            test_result = result.get("test_result", {})

            if test_result:
                output = test_result.get("output", "")
                passed_count = self._count_passed(output)
                total_count = self._count_total(output)

                if total_count == 0:
                    passed = test_result.get("passed", False)
                    if passed:
                        logger.info("Tests passed (no count available)")
                        return {"status": "success", "tests_passed": True}
                    else:
                        logger.warning("Tests failed (no count available)")
                        return {"status": "failed", "error": "Tests failed"}

                success_rate = (
                    passed_count / total_count * 100 if total_count > 0 else 0
                )

                if success_rate == 100:
                    logger.info("All tests passed (%d/%d)", total_count, total_count)
                    return {"status": "success", "tests_passed": True}
                else:
                    logger.info(
                        "Partial success: %d/%d tests passed (%.0f%%)",
                        passed_count,
                        total_count,
                        success_rate,
                    )
                    return {
                        "status": "partial" if success_rate >= 50 else "low_success",
                        "passed_count": passed_count,
                        "total_count": total_count,
                        "success_rate": success_rate,
                    }

            if result.get("status") == "skipped":
                logger.info("Skipped: %s", result.get("reason", "Unknown"))
                return {"status": "skipped", "reason": result.get("reason")}

            logger.warning("Failed: %s", result.get("error", "Unknown error"))
            return {"status": "failed", "error": result.get("error")}

        except Exception as e:
            logger.error("Error processing %s: %s", file_path, e, exc_info=True)
            return {"status": "error", "error": str(e)}

    def _count_passed(self, pytest_output: str) -> int:
        """Extract passed test count from pytest output."""
        import re

        match = re.search("(\\d+) passed", pytest_output)
        return int(match.group(1)) if match else 0

    def _count_total(self, pytest_output: str) -> int:
        """Extract total test count from pytest output."""
        import re

        passed_match = re.search("(\\d+) passed", pytest_output)
        failed_match = re.search("(\\d+) failed", pytest_output)
        passed = int(passed_match.group(1)) if passed_match else 0
        failed = int(failed_match.group(1)) if failed_match else 0
        return passed + failed

    def _log_summary(self, results: list[dict]):
        """Log summary of results."""
        success_count = 0
        partial_count = 0
        failed_count = 0
        skipped_count = 0

        for result in results:
            status = result.get("status", "unknown")
            if status == "success":
                success_count += 1
            elif status in ("partial", "low_success"):
                partial_count += 1
            elif status == "skipped":
                skipped_count += 1
            else:
                failed_count += 1

        logger.info(
            "Batch Summary: Success=%d, Partial=%d, Failed=%d, Skipped=%d",
            success_count,
            partial_count,
            failed_count,
            skipped_count,
        )


async def _remediate_batch(
    cognitive_service: CognitiveService,
    auditor_context: AuditorContext,
    count: int,
    max_complexity: str = "MODERATE",
) -> dict[str, Any]:
    """
    Entry point for batch remediation.
    """
    service = BatchRemediationService(
        cognitive_service, auditor_context, max_complexity=max_complexity
    )
    return await service.process_batch(count)
