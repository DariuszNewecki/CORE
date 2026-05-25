# src/will/workers/test_runner_sensor.py
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
    uncovered_source_files,
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

        # Load coverage config once per cycle so every mapping below
        # shares one consistent policy snapshot. Drain also uses it.
        config = load_test_coverage_config()

        if not findings:
            await self._adjudicate_test_quarantine(config)
            await self.post_report(
                subject="test_runner_sensor.run.complete",
                payload={"message": "No test.run_required findings to process."},
            )
            return

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

        # ADR-072 D5: drain test.missing and test.failure quarantine after
        # processing this cycle's queue. Reuses the just-loaded config so
        # the source-tree walk for test.missing matches the policy snapshot
        # the queue loop used.
        await self._adjudicate_test_quarantine(config)

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

    # -------------------------------------------------------------------------
    # Quarantine drain — ADR-072 D5
    # -------------------------------------------------------------------------

    # ID: 4a2c8f5e-9d1b-4607-b3a8-7e9f0c1d2e34
    async def _adjudicate_test_quarantine(self, config: dict[str, Any]) -> None:
        """
        Drain the awaiting_reaudit quarantine for test.missing and
        test.failure namespaces (ADR-072 D5).

        - test.missing: re-walks source_root via uncovered_source_files;
          subjects of currently-uncovered files form current_subjects.
          Quarantined rows whose source file is still uncovered are
          released back to 'open'; rows whose source is now covered (or
          was deleted) are resolved.

        - test.failure: enumerates test_files referenced by quarantined
          rows, re-runs pytest on each, and rebuilds current_subjects
          from the FAILED output. Quarantined rows whose test still
          fails are released; rows whose test now passes (or whose
          test_file was deleted) are resolved. A pytest infrastructure
          failure for a given test_file keeps the related subjects in
          current_subjects so they are released back to 'open' rather
          than resolved without evidence.
        """
        from body.services.service_registry import service_registry

        bb_svc = await service_registry.get_blackboard_service()

        # --- test.missing drain ----------------------------------------------
        uncovered = uncovered_source_files(self._repo_root, config)
        missing_current = {f"test.missing::{src}" for src in uncovered}

        missing_reaudit = await bb_svc.adjudicate_awaiting_reaudit_findings(
            subject_prefix="test.missing",
            current_violation_subjects=missing_current,
            resolved_by="test_runner_sensor",
        )
        missing_released = len(missing_reaudit["released_subjects"])
        missing_resolved = len(missing_reaudit["resolved_subjects"])

        if missing_released or missing_resolved:
            logger.info(
                "TestRunnerSensor: test.missing reaudit drained %d released, %d resolved.",
                missing_released,
                missing_resolved,
            )
            await self.post_report(
                subject="audit.reaudit.complete::test.missing",
                payload={
                    "namespace": "test.missing",
                    "released_count": missing_released,
                    "resolved_count": missing_resolved,
                    "released_subjects": missing_reaudit["released_subjects"],
                    "resolved_subjects": missing_reaudit["resolved_subjects"],
                },
            )

        # --- test.failure drain ----------------------------------------------
        failure_quarantined = await bb_svc.fetch_awaiting_reaudit_subjects_by_prefix(
            "test.failure::%"
        )
        if not failure_quarantined:
            return

        # Group quarantined subjects by their test_file so each file is
        # only re-run once even if it has multiple failing test_names.
        # Subject format: test.failure::<test_file>::<test_name>
        by_test_file: dict[str, list[str]] = {}
        for subject in failure_quarantined:
            parts = subject.split("::")
            if len(parts) < 3:
                continue
            by_test_file.setdefault(parts[1], []).append(subject)

        failure_current: set[str] = set()

        try:
            from shared.path_resolver import PathResolver
            from will.phases.canary.pytest_runner import PytestRunner

            path_resolver = PathResolver.from_repo(
                self._repo_root, self._repo_root / ".intent"
            )
            runner = PytestRunner(path_resolver)
        except Exception as exc:
            logger.warning(
                "TestRunnerSensor: pytest runner unavailable for test.failure "
                "drain (%s) — keeping all quarantined subjects in current set "
                "to avoid spurious resolve.",
                exc,
            )
            for subjects in by_test_file.values():
                failure_current.update(subjects)
            by_test_file = {}

        for test_file, quarantined_subjects in by_test_file.items():
            test_path = self._repo_root / test_file
            if not test_path.exists():
                # Deleted test_file: leave subjects out of current → resolved.
                continue

            try:
                result = await runner.run_tests([test_file])
            except Exception as exc:
                logger.warning(
                    "TestRunnerSensor: pytest run failed for %s during "
                    "reaudit (%s) — keeping subjects in current set to "
                    "avoid spurious resolve.",
                    test_file,
                    exc,
                )
                failure_current.update(quarantined_subjects)
                continue

            exit_code = result.get("exit_code", 1)
            if exit_code == 0:
                continue  # all green → leave out of current → resolved

            output = result.get("output", "")
            failed_test_names = set(_FAILED_TEST_PATTERN.findall(output))

            for subject in quarantined_subjects:
                parts = subject.split("::")
                test_name = parts[2] if len(parts) >= 3 else "unknown"
                if test_name == "unknown":
                    # Original was posted as ::unknown when failures were
                    # unparseable. If pytest still reports failure for the
                    # file, the ::unknown subject remains "still failing".
                    failure_current.add(subject)
                elif test_name in failed_test_names:
                    failure_current.add(subject)

        failure_reaudit = await bb_svc.adjudicate_awaiting_reaudit_findings(
            subject_prefix="test.failure",
            current_violation_subjects=failure_current,
            resolved_by="test_runner_sensor",
        )
        failure_released = len(failure_reaudit["released_subjects"])
        failure_resolved = len(failure_reaudit["resolved_subjects"])

        if failure_released or failure_resolved:
            logger.info(
                "TestRunnerSensor: test.failure reaudit drained %d released, %d resolved.",
                failure_released,
                failure_resolved,
            )
            await self.post_report(
                subject="audit.reaudit.complete::test.failure",
                payload={
                    "namespace": "test.failure",
                    "released_count": failure_released,
                    "resolved_count": failure_resolved,
                    "released_subjects": failure_reaudit["released_subjects"],
                    "resolved_subjects": failure_reaudit["resolved_subjects"],
                },
            )
