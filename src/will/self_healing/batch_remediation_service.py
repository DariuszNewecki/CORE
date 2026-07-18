# src/will/self_healing/batch_remediation_service.py

"""
Batch test generation service for processing multiple files efficiently.

Selects files by lowest coverage and complexity threshold, processes them
in order, and provides progress reporting.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from body.quality.coverage_analyzer import CoverageAnalyzer
from body.services.file_service import FileService
from mind.governance.audit_context import AuditorContext
from shared.infrastructure.config_service import ConfigService
from shared.infrastructure.intent.operational_config import load_operational_config
from shared.logger import getLogger
from will.orchestration.cognitive_service import CognitiveService
from will.self_healing.single_file_remediation import (
    EnhancedSingleFileRemediationService,
)


logger = getLogger(__name__)

_CFG = load_operational_config().coverage


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
        file_handler: FileService,
        config_service: ConfigService | None = None,
        max_complexity: str = "MODERATE",
    ):
        from body.self_healing.complexity_filter import ComplexityFilter

        self.cognitive = cognitive_service
        self.auditor = auditor_context
        self.file_handler = file_handler
        self.config_service = config_service
        self.max_complexity = max_complexity
        self.analyzer: CoverageAnalyzer | None = None
        self.repo_root: Path | None = None
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
        await self._ensure_runtime_config()
        logger.info("Batch Remediation: Finding candidate files...")
        candidates = self._get_candidate_files()

        if not candidates:
            logger.warning("No suitable files found for testing")
            return {
                "status": "no_candidates",
                "processed": 0,
                "results": [],
                "summary": {"success": 0, "failed": 0, "skipped": 0},
            }

        logger.info(
            "Found %d files below %.1f%% coverage. Filtering by complexity: %s",
            len(candidates),
            _CFG.batch_remediation_threshold_pct,
            self.max_complexity,
        )

        filtered = self._filter_by_complexity(candidates)
        if not filtered:
            logger.warning(
                "No files match complexity threshold: %s", self.max_complexity
            )
            return {
                "status": "no_matches",
                "processed": 0,
                "results": [],
                "summary": {"success": 0, "failed": 0, "skipped": 0},
            }

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

        summary = self._summarize(results)
        return {
            "status": "completed",
            "processed": len(results),
            "results": results,
            "summary": summary,
        }

    def _get_candidate_files(self) -> list[tuple[Path, float]]:
        """Get files with coverage data, sorted by lowest coverage first."""
        if self.analyzer is None or self.repo_root is None:
            return []
        coverage_data = self.analyzer.get_module_coverage()
        if not coverage_data:
            return []
        candidates = [
            (self.repo_root / path, percent)
            for path, percent in coverage_data.items()
            if path.startswith("src/")
            and percent < _CFG.batch_remediation_threshold_pct
        ]
        candidates.sort(key=lambda x: x[1])
        return candidates

    async def _ensure_runtime_config(self) -> None:
        """Initialize repo-root dependent services once."""
        if self.repo_root is not None and self.analyzer is not None:
            return

        if self.config_service is not None:
            repo_root_str = await self.config_service.get("REPO_PATH", required=True)
            self.repo_root = Path(repo_root_str)
        else:
            self.repo_root = self.auditor.repo_path

        self.analyzer = CoverageAnalyzer(repo_path=self.repo_root)

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
        """Process a single file.

        Reads the real keys EnhancedSingleFileRemediationService.remediate()
        returns ("status" in {"completed", "failed", "skipped", "error"}) —
        a prior version of this method checked a "test_result" key that
        producer never returned, so every file silently reported "failed"
        regardless of outcome (#813).
        """
        if self.repo_root is None:
            # _ensure_runtime_config() populates repo_root before any file is
            # processed via process_batch(); guard the standalone path too.
            return {"status": "error", "error": "repo_root not initialized"}
        try:
            service = EnhancedSingleFileRemediationService(
                self.cognitive,
                self.auditor,
                file_path,
                file_handler=self.file_handler,
                repo_root=self.repo_root,
                max_complexity=self.max_complexity,
            )
            result = await service.remediate()

            if result.get("status") == "completed":
                logger.info("Tests generated successfully: %s", file_path)
                return {
                    "status": "success",
                    "test_file": result.get("test_file"),
                    "final_coverage": result.get("final_coverage"),
                }

            if result.get("status") == "skipped":
                logger.info("Skipped: %s", result.get("reason", "Unknown"))
                return {"status": "skipped", "reason": result.get("reason")}

            logger.warning("Failed: %s", result.get("error", "Unknown error"))
            return {"status": "failed", "error": result.get("error")}

        except Exception as e:
            logger.error("Error processing %s: %s", file_path, e, exc_info=True)
            return {"status": "error", "error": str(e)}

    def _summarize(self, results: list[dict]) -> dict[str, int]:
        """Count per-file outcomes and log the summary. Returns the counts
        so callers (coverage_runner.py, the CLI) can render them — #813."""
        success_count = 0
        failed_count = 0
        skipped_count = 0

        for result in results:
            status = result.get("status", "unknown")
            if status == "success":
                success_count += 1
            elif status == "skipped":
                skipped_count += 1
            else:
                failed_count += 1

        logger.info(
            "Batch Summary: Success=%d, Failed=%d, Skipped=%d",
            success_count,
            failed_count,
            skipped_count,
        )
        return {
            "success": success_count,
            "failed": failed_count,
            "skipped": skipped_count,
        }
