# src/will/workers/test_coverage_sensor.py
"""
TestCoverageSensor - Test Coverage Gap Sensing Worker.

Responsibility: Scan the declared source root for Python files with no
corresponding test file and post a `python::test.coverage::<source_file>`
finding for each gap (ADR-091 D2 canonical subject format).
TestRunnerSensor consumes these findings, confirms the gap via pytest,
and posts `python::test.runner.missing` for downstream remediation by
TestRemediatorWorker.

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

from pathlib import Path
from typing import Any

from shared.infrastructure.intent.test_coverage_paths import (
    load_test_coverage_config,
    uncovered_source_files,
)
from shared.logger import getLogger
from shared.workers.scheduled_worker import ScheduledWorker


logger = getLogger(__name__)


# ID: f7e8d9c0-b1a2-4345-8901-234567890abc
class TestCoverageSensor(ScheduledWorker):
    """
    Sensing worker. Scans the declared source root for Python source files
    with no corresponding test file, and posts a `python::test.coverage`
    finding for each gap (ADR-091 D2 canonical subject format). Scan
    config is read from .intent/ at runtime.

    No LLM calls. No file writes. approval_required: false.
    """

    declaration_name = "test_coverage_sensor"

    def __init__(self, core_context: Any = None) -> None:
        super().__init__()

        # ADR-091 D1: artifact_type and rule_namespace are required on every
        # class:sensing worker. D5 Phase 5 routes subject construction through
        # the declared values rather than a hardcoded prefix; the canonical
        # subject becomes `<artifact_type>::<rule_namespace>::<source_file>`.
        scope = self._declaration["mandate"]["scope"]
        self._artifact_type: str = scope["artifact_type"][0]
        self._rule_namespace: str = scope["rule_namespace"]

        from shared.infrastructure.bootstrap_registry import BootstrapRegistry

        self._repo_root: Path = BootstrapRegistry.get_repo_path()
        self._core_context = core_context

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
            subject = f"{self._artifact_type}::{self._rule_namespace}::{source_file}"
            if subject in existing:
                skipped += 1
                logger.debug("TestCoverageSensor: skipping already-posted %s", subject)
                continue

            await self.post_artifact_finding(
                artifact_type=self._artifact_type,
                sub_namespace=self._rule_namespace,
                identity_key_value=source_file,
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

        Delegates to shared.infrastructure.intent.test_coverage_paths
        .uncovered_source_files — same helper is used by TestRunnerSensor
        to build current_subjects for the `python::test.runner.missing`
        quarantine drain (ADR-072 D5).
        """
        return uncovered_source_files(self._repo_root, config)

    # -------------------------------------------------------------------------
    # Blackboard helpers
    # -------------------------------------------------------------------------

    # ID: e6f7a8b9-c0d1-4234-3456-789012345f01
    async def _fetch_existing_subjects(self) -> set[str]:
        """
        Fetch active `python::test.coverage::*` subjects from the Blackboard.
        Dedup is by subject content across all workers, not by this
        worker's UUID — prevents re-posting across daemon restarts.
        ADR-091 D2 canonical format: keys are
        `<artifact_type>::<rule_namespace>::%`.
        """
        from body.services.service_registry import service_registry

        svc = await service_registry.get_blackboard_service()
        return await svc.fetch_active_finding_subjects_by_prefix(
            f"{self._artifact_type}::{self._rule_namespace}::%"
        )
