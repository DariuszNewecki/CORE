# src/will/workers/test_runner_sensor.py
# ID: will.workers.test_runner_sensor
"""
TestRunnerSensor - Post-Execution Test Verification Worker.

Responsibility: Consume test.run_required findings from the blackboard,
run pytest on existing test files, and post test.failure or test.missing
findings for downstream remediation.

Source->test mapping is governed by
.intent/enforcement/config/test_coverage.yaml and resolved through
shared.infrastructure.intent.test_coverage_paths.source_to_test_path —
never hardcoded in this file.

Constitutional standing:
- Declaration:      .intent/workers/test_runner_sensor.yaml
- Class:            sensing
- Phase:            audit
- Permitted tools:  none — pytest execution only
- Approval:         false — findings are observations only

Self-scheduling: TestRunnerSensor manages its own asyncio loop via
run_loop(). Sanctuary starts run_loop() once on bootstrap.

LAYER: will/workers — sensing worker. Reads Blackboard. Runs pytest.
Posts findings to Blackboard. No LLM. No direct file writes.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

from shared.infrastructure.intent.test_coverage_paths import (
    load_test_coverage_config,
    source_to_test_path,
)
from shared.logger import getLogger
from shared.workers.base import Worker


logger = getLogger(__name__)

_SUBJECT_PREFIX = "test.run_required::"
_FAILED_TEST_PATTERN = re.compile(r"FAILED (tests/\S+)")


# ID: 3a7c9e1b-d4f2-4680-b8a5-6e0f2c3d5a19
class TestRunnerSensor(Worker):
    """
    Sensing worker. Consumes test.run_required blackboard findings,
    runs pytest on existing test files, and posts test.failure or
    test.missing findings for downstream remediation.

    No LLM calls. No direct file writes. approval_required: false.
    """

    declaration_name = "test_runner_sensor"

    def __init__(self, core_context: Any = None) -> None:
        super().__init__()
        schedule = self._declaration.get("mandate", {}).get("schedule", {})
        self._max_interval: int = schedule.get("max_interval", 300)
        self._glide_off: int = schedule.get(
            "glide_off", max(int(self._max_interval * 0.10), 10)
        )

        from shared.infrastructure.bootstrap_registry import BootstrapRegistry

        self._repo_root: Path = BootstrapRegistry.get_repo_path()
        self._core_context = core_context

    # -------------------------------------------------------------------------
    # Self-scheduling entry point — called once by Sanctuary
    # -------------------------------------------------------------------------

    # ID: 5b8d0f2a-e6c3-4791-a9d7-7f1a3e4c6b82
    async def run_loop(self) -> None:
        """
        Continuous self-scheduling loop. Runs one sensing cycle per
        max_interval seconds. Sanctuary calls this once on bootstrap.
        """
        logger.info(
            "TestRunnerSensor: starting loop (max_interval=%ds, glide_off=%ds)",
            self._max_interval,
            self._glide_off,
        )
        await self._register()

        while True:
            try:
                await self.run()
            except Exception as exc:
                logger.error("TestRunnerSensor: cycle failed: %s", exc, exc_info=True)
                try:
                    await self._post_entry(
                        entry_type="report",
                        subject="test_runner_sensor.cycle_error",
                        payload={"error": str(exc)},
                        status="abandoned",
                    )
                except Exception:
                    logger.exception("TestRunnerSensor: failed to post error report")

            await asyncio.sleep(self._max_interval)

    # -------------------------------------------------------------------------
    # Single sensing cycle
    # -------------------------------------------------------------------------

    # ID: 7c9e1a3b-f5d4-4802-b6a8-8e2b4f5d7c93
    async def run(self) -> None:
        """
        Execute one test-sensing cycle:
        1. Post heartbeat
        2. Fetch open test.run_required findings
        3. For each: check test file exists, run pytest or post test.missing
        4. Post completion report
        """
        await self.post_heartbeat()

        findings = await self._fetch_run_required_findings()

        if not findings:
            await self.post_report(
                subject="test_runner_sensor.run.complete",
                payload={"message": "No test.run_required findings to process."},
            )
            return

        # Load coverage config once per cycle so every mapping below
        # shares one consistent policy snapshot.
        config = load_test_coverage_config()

        count_run = 0
        count_passed = 0
        count_failed = 0
        count_missing = 0

        from body.services.service_registry import service_registry

        svc = await service_registry.get_blackboard_service()

        for finding in findings:
            entry_id = finding["id"]
            payload = finding.get("payload", {})
            source_file = payload.get("source_file", "")

            if not source_file:
                await svc.resolve_entries([entry_id])
                continue

            # Map source_file to test_file via governed policy.
            try:
                test_file = source_to_test_path(source_file, config)
            except ValueError:
                await svc.resolve_entries([entry_id])
                continue

            test_path = self._repo_root / test_file

            if not test_path.exists():
                # Post test.missing finding
                await self.post_finding(
                    subject=f"test.missing::{source_file}",
                    payload={
                        "source_file": source_file,
                        "test_file": test_file,
                    },
                )
                await svc.resolve_entries([entry_id])
                count_missing += 1
                continue

            # Run pytest on the test file
            try:
                from shared.path_resolver import PathResolver
                from will.phases.canary.pytest_runner import PytestRunner

                path_resolver = PathResolver.from_repo(
                    self._repo_root, self._repo_root / ".intent"
                )
                runner = PytestRunner(path_resolver)
                result = await runner.run_tests([test_file])
            except Exception as e:
                logger.error(
                    "TestRunnerSensor: pytest execution failed for %s: %s",
                    test_file,
                    e,
                )
                await svc.resolve_entries([entry_id])
                continue

            count_run += 1
            exit_code = result.get("exit_code", 1)
            output = result.get("output", "")

            if exit_code != 0:
                # Parse FAILED test names from output
                failed_tests = _FAILED_TEST_PATTERN.findall(output)
                for test_name in failed_tests:
                    await self.post_finding(
                        subject=f"test.failure::{test_file}::{test_name}",
                        payload={
                            "source_file": source_file,
                            "test_file": test_file,
                            "test_name": test_name,
                            "output": output[:2000],
                        },
                    )
                    count_failed += 1

                if not failed_tests:
                    # exit_code != 0 but no FAILED pattern matched
                    await self.post_finding(
                        subject=f"test.failure::{test_file}::unknown",
                        payload={
                            "source_file": source_file,
                            "test_file": test_file,
                            "test_name": "unknown",
                            "output": output[:2000],
                        },
                    )
                    count_failed += 1
            else:
                count_passed += result.get("passed", 0)

            # Resolve the test.run_required entry regardless of pass/fail
            await svc.resolve_entries([entry_id])

        await self.post_report(
            subject="test_runner_sensor.run.complete",
            payload={
                "run": count_run,
                "passed": count_passed,
                "failed": count_failed,
                "missing": count_missing,
            },
        )
        logger.info(
            "TestRunnerSensor: cycle complete — run=%d passed=%d failed=%d missing=%d",
            count_run,
            count_passed,
            count_failed,
            count_missing,
        )

    # -------------------------------------------------------------------------
    # DB reads — delegated to BlackboardService
    # -------------------------------------------------------------------------

    async def _fetch_run_required_findings(self) -> list[dict[str, Any]]:
        """Fetch open test.run_required findings from the blackboard."""
        from body.services.service_registry import service_registry

        svc = await service_registry.get_blackboard_service()
        return await svc.fetch_open_findings(
            prefix=f"{_SUBJECT_PREFIX}%",
            limit=50,
        )
