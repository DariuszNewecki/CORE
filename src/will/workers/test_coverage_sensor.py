# src/will/workers/test_coverage_sensor.py
# ID: will.workers.test_coverage_sensor
"""
TestCoverageSensor - Test Coverage Gap Sensing Worker.

Responsibility: Scan the declared source root for Python files with no
corresponding test file and post a test.run_required finding for each gap.
TestRunnerSensor consumes these findings, confirms the gap via pytest,
and posts test.missing for downstream remediation by ViolationRemediatorWorker.

Scan behaviour is governed entirely by
.intent/enforcement/config/test_coverage.yaml — no paths or exclusions
are hardcoded in this file. All source->test mapping flows through
shared.infrastructure.intent.test_coverage_paths.source_to_test_path.

Constitutional standing:
- Declaration:      .intent/workers/test_coverage_sensor.yaml
- Class:            sensing
- Phase:            audit
- Permitted tools:  none — filesystem scan only
- Approval:         false — findings are observations only

Self-scheduling: manages its own asyncio loop via run_loop().
Sanctuary starts run_loop() once on bootstrap.

LAYER: will/workers — sensing worker. Reads filesystem and .intent/.
Posts findings to Blackboard. No LLM. No file writes.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from shared.infrastructure.intent.test_coverage_paths import (
    load_test_coverage_config,
    source_to_test_path,
)
from shared.logger import getLogger
from shared.workers.base import Worker


logger = getLogger(__name__)

_SUBJECT_PREFIX = "test.run_required"


# ID: f7e8d9c0-b1a2-4345-8901-234567890abc
class TestCoverageSensor(Worker):
    """
    Sensing worker. Scans the declared source root for Python source files
    with no corresponding test file, and posts a test.run_required finding
    for each gap. Scan config is read from .intent/ at runtime.

    No LLM calls. No file writes. approval_required: false.
    """

    declaration_name = "test_coverage_sensor"

    def __init__(self, core_context: Any = None) -> None:
        super().__init__()
        schedule = self._declaration.get("mandate", {}).get("schedule", {})
        self._max_interval: int = schedule.get("max_interval", 600)
        self._glide_off: int = schedule.get(
            "glide_off", max(int(self._max_interval * 0.10), 10)
        )

        from shared.infrastructure.bootstrap_registry import BootstrapRegistry

        self._repo_root: Path = BootstrapRegistry.get_repo_path()
        self._core_context = core_context

    # ID: a2b3c4d5-e6f7-4890-9012-345678901bcd
    async def run_loop(self) -> None:
        """
        Continuous self-scheduling loop. Runs one sensing cycle per
        max_interval seconds. Sanctuary calls this once on bootstrap.
        """
        logger.info(
            "TestCoverageSensor: starting loop (max_interval=%ds, glide_off=%ds)",
            self._max_interval,
            self._glide_off,
        )
        await self._register()

        while True:
            try:
                await self.run()
            except Exception as exc:
                logger.error("TestCoverageSensor: cycle failed: %s", exc, exc_info=True)
            await asyncio.sleep(self._max_interval)

    # ID: b3c4d5e6-f7a8-4901-0123-456789012cde
    async def run(self) -> None:
        """
        Execute one coverage-sensing cycle:
        1. Post heartbeat
        2. Load scan config from .intent/
        3. Scan source root for untested files
        4. Dedup against existing Blackboard findings
        5. Post findings for new gaps
        6. Post completion report
        """
        await self.post_heartbeat()

        config = self._load_coverage_config()
        uncovered = self._scan_uncovered_files(config)

        if not uncovered:
            await self.post_report(
                subject="test_coverage_sensor.run.complete",
                payload={
                    "uncovered": 0,
                    "message": "All source files have corresponding test files.",
                },
            )
            logger.info("TestCoverageSensor: no coverage gaps found.")
            return

        logger.info(
            "TestCoverageSensor: %d uncovered file(s) detected.", len(uncovered)
        )

        existing = await self._fetch_existing_subjects()

        posted = 0
        skipped = 0

        for source_file in sorted(uncovered):
            subject = f"{_SUBJECT_PREFIX}::{source_file}"
            if subject in existing:
                skipped += 1
                logger.debug("TestCoverageSensor: skipping already-posted %s", subject)
                continue

            await self.post_finding(
                subject=subject,
                payload={"source_file": source_file},
            )
            posted += 1
            logger.debug("TestCoverageSensor: posted finding for %s", source_file)

        await self.post_report(
            subject="test_coverage_sensor.run.complete",
            payload={
                "uncovered": len(uncovered),
                "posted": posted,
                "skipped_dedup": skipped,
            },
        )
        logger.info(
            "TestCoverageSensor: cycle complete — %d posted, %d skipped (dedup).",
            posted,
            skipped,
        )

    # -------------------------------------------------------------------------
    # Config loader — thin wrapper around the shared policy-governed helper
    # -------------------------------------------------------------------------

    # ID: c4d5e6f7-a8b9-4012-1234-567890123def
    def _load_coverage_config(self) -> dict[str, Any]:
        """
        Load scan configuration from
        .intent/enforcement/config/test_coverage.yaml.

        Delegates to shared.infrastructure.intent.test_coverage_paths so
        all config access flows through the same policy-governed helper.
        """
        return load_test_coverage_config()

    # -------------------------------------------------------------------------
    # Filesystem scan
    # -------------------------------------------------------------------------

    # ID: d5e6f7a8-b9c0-4123-2345-678901234ef0
    def _scan_uncovered_files(self, config: dict[str, Any]) -> list[str]:
        """
        Walk source_root and return relative paths (from repo root) for
        Python source files that have no corresponding test file.

        Mapping is driven entirely by config loaded from .intent/ via
        source_to_test_path:
          {source_root}/foo/bar.py
            → {test_root}/foo/bar{test_file_suffix}
        """
        source_root_rel: str = config.get("source_root", "src")
        excluded: frozenset[str] = frozenset(
            config.get("excluded_filenames", ["__init__.py"])
        )
        include_files: frozenset[str] = frozenset(config.get("include_files") or [])

        src_root = self._repo_root / source_root_rel
        if not src_root.exists():
            logger.warning("TestCoverageSensor: source root not found at %s", src_root)
            return []

        uncovered: list[str] = []

        for py_file in src_root.rglob("*.py"):
            if py_file.name in excluded:
                continue

            # Relative path from repo root, e.g. src/foo/bar.py
            rel = py_file.relative_to(self._repo_root)
            source_file = str(rel)

            if include_files and source_file not in include_files:
                continue

            try:
                test_rel = source_to_test_path(source_file, config)
            except ValueError:
                continue  # skip files outside configured source_root

            test_path = self._repo_root / test_rel

            if not test_path.exists():
                uncovered.append(source_file)

        return uncovered

    # -------------------------------------------------------------------------
    # Blackboard helpers
    # -------------------------------------------------------------------------

    # ID: e6f7a8b9-c0d1-4234-3456-789012345f01
    async def _fetch_existing_subjects(self) -> set[str]:
        """
        Fetch active test.run_required subjects from the Blackboard.
        Dedup is by subject content across all workers, not by this
        worker's UUID — prevents re-posting across daemon restarts.
        """
        from body.services.service_registry import service_registry

        svc = await service_registry.get_blackboard_service()
        return await svc.fetch_active_finding_subjects_by_prefix(
            f"{_SUBJECT_PREFIX}::%"
        )
