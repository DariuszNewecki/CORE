# src/will/workers/test_runner_sensor.py
"""
TestRunnerSensor - Post-Execution Test Verification Worker.

Responsibility: Consume `python::test.coverage::*` findings from the
blackboard, run pytest on existing test files, and post
`python::test.runner.failure::*` or `python::test.runner.missing::*`
findings for downstream remediation (ADR-091 D2 canonical subject format).

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
import time
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

_FAILED_TEST_PATTERN = re.compile(r"FAILED (tests/\S+)")

# ADR-091 D2: TestRunnerSensor consumes findings emitted by
# TestCoverageSensor under the canonical `python::test.coverage::*` shape,
# and emits two sub_namespaces under its own declared `test.runner`
# rule_namespace per D2's dotted-extension allowance.
_COVERAGE_CONSUMER_PREFIX = "python::test.coverage::"
_MISSING_REAUDIT_PREFIX = "python::test.runner.missing"
_FAILURE_REAUDIT_PREFIX = "python::test.runner.failure"


# ID: 3a7c9e1b-d4f2-4680-b8a5-6e0f2c3d5a19
class TestRunnerSensor(Worker):
    """
    Sensing worker. Consumes `python::test.coverage` blackboard findings,
    runs pytest on existing test files, and posts
    `python::test.runner.failure` or `python::test.runner.missing` findings
    for downstream remediation (ADR-091 D2 canonical subject format).

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

        # ADR-091 D1: artifact_type + rule_namespace required on class:sensing.
        # The two sub_namespaces emitted (`test.runner.missing` and
        # `test.runner.failure`) extend the declared `test.runner` rule_namespace
        # per D2's dotted-extension allowance.
        scope = self._declaration["mandate"]["scope"]
        self._artifact_type: str = scope["artifact_type"][0]
        self._rule_namespace: str = scope["rule_namespace"]

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
            cycle_start = time.monotonic()
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

            elapsed = time.monotonic() - cycle_start
            await asyncio.sleep(max(self._max_interval - elapsed, 0))

    # -------------------------------------------------------------------------
    # Single sensing cycle
    # -------------------------------------------------------------------------

    # ID: 7c9e1a3b-f5d4-4802-b6a8-8e2b4f5d7c93
    async def run(self) -> None:
        """
        Execute one test-sensing cycle:
        1. Post heartbeat
        2. Fetch open `python::test.coverage::*` findings
        3. For each: check test file exists, run pytest or post `python::test.runner.missing`
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
                payload={"message": "No test.coverage findings to process."},
            )
            return

        count_run = 0
        count_passed = 0
        count_failed = 0
        count_missing = 0

        from body.services.service_registry import service_registry

        svc = await service_registry.get_blackboard_service()

        # Fetch once per cycle; skip posting if the subject is already open.
        existing_missing = await svc.fetch_active_finding_subjects_by_prefix(
            f"{self._artifact_type}::{self._rule_namespace}.missing::%"
        )

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
                # Post python::test.runner.missing finding (ADR-091 D2),
                # but only if one is not already open for this source file.
                missing_subject = (
                    f"{self._artifact_type}"
                    f"::{self._rule_namespace}.missing"
                    f"::{source_file}"
                )
                if missing_subject not in existing_missing:
                    await self.post_artifact_finding(
                        artifact_type=self._artifact_type,
                        sub_namespace=f"{self._rule_namespace}.missing",
                        identity_key_value=source_file,
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
                # Parse FAILED test names from output. Post under
                # python::test.runner.failure with identity key
                # `<test_file>::<test_name>` (ADR-091 D2).
                failed_tests = _FAILED_TEST_PATTERN.findall(output)
                for test_name in failed_tests:
                    await self.post_artifact_finding(
                        artifact_type=self._artifact_type,
                        sub_namespace=f"{self._rule_namespace}.failure",
                        identity_key_value=f"{test_file}::{test_name}",
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
                    await self.post_artifact_finding(
                        artifact_type=self._artifact_type,
                        sub_namespace=f"{self._rule_namespace}.failure",
                        identity_key_value=f"{test_file}::unknown",
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

            # Resolve the python::test.coverage entry regardless of pass/fail
            await svc.resolve_entries([entry_id])

        # ADR-072 D5: drain python::test.runner.missing and python::test.runner.failure
        # quarantine after processing this cycle's queue. Reuses the just-loaded
        # config so the source-tree walk for python::test.runner.missing matches
        # the policy snapshot the queue loop used.
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
        """Fetch open `python::test.coverage::*` findings from the blackboard.

        These are emitted by TestCoverageSensor (ADR-091 D2 canonical format).
        TestRunnerSensor consumes them, runs pytest, and emits its own
        `python::test.runner.missing|failure` findings.
        """
        from body.services.service_registry import service_registry

        svc = await service_registry.get_blackboard_service()
        return await svc.fetch_open_findings(
            prefix=f"{_COVERAGE_CONSUMER_PREFIX}%",
            limit=50,
        )

    # -------------------------------------------------------------------------
    # Quarantine drain — ADR-072 D5
    # -------------------------------------------------------------------------

    # ID: 4a2c8f5e-9d1b-4607-b3a8-7e9f0c1d2e34
    async def _adjudicate_test_quarantine(self, config: dict[str, Any]) -> None:
        """
        Drain the awaiting_reaudit quarantine for the two test sub_namespaces
        (`python::test.runner.missing` and `python::test.runner.failure`) per
        ADR-072 D5 + ADR-091 D2 canonical format.

        - missing: re-walks source_root via uncovered_source_files;
          subjects of currently-uncovered files form current_subjects.
          Quarantined rows whose source file is still uncovered are
          released back to 'open'; rows whose source is now covered (or
          was deleted) are resolved.

        - failure: enumerates test_files referenced by quarantined
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

        # --- python::test.runner.missing drain -------------------------------
        uncovered = uncovered_source_files(self._repo_root, config)
        missing_current = {f"{_MISSING_REAUDIT_PREFIX}::{src}" for src in uncovered}

        missing_reaudit = await bb_svc.adjudicate_awaiting_reaudit_findings(
            subject_prefix=_MISSING_REAUDIT_PREFIX,
            current_violation_subjects=missing_current,
            resolved_by="test_runner_sensor",
        )
        missing_released = len(missing_reaudit["released_subjects"])
        missing_resolved = len(missing_reaudit["resolved_subjects"])

        if missing_released or missing_resolved:
            logger.info(
                "TestRunnerSensor: test.runner.missing reaudit drained %d released, %d resolved.",
                missing_released,
                missing_resolved,
            )
            await self.post_report(
                subject="audit.reaudit.complete::test.runner.missing",
                payload={
                    "namespace": "test.runner.missing",
                    "released_count": missing_released,
                    "resolved_count": missing_resolved,
                    "released_subjects": missing_reaudit["released_subjects"],
                    "resolved_subjects": missing_reaudit["resolved_subjects"],
                },
            )

        # --- python::test.runner.failure drain -------------------------------
        failure_quarantined = await bb_svc.fetch_awaiting_reaudit_subjects_by_prefix(
            f"{_FAILURE_REAUDIT_PREFIX}::%"
        )
        if not failure_quarantined:
            return

        # Group quarantined subjects by their test_file so each file is
        # only re-run once even if it has multiple failing test_names.
        # Subject format (ADR-091 D2):
        #   python::test.runner.failure::<test_file>::<test_name>
        # parts indices: 0=python, 1=test.runner.failure, 2=test_file, 3=test_name
        by_test_file: dict[str, list[str]] = {}
        for subject in failure_quarantined:
            parts = subject.split("::")
            if len(parts) < 4:
                continue
            by_test_file.setdefault(parts[2], []).append(subject)

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
                "TestRunnerSensor: pytest runner unavailable for python::test.runner.failure "
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
                # parts indices: 0=python, 1=test.runner.failure,
                # 2=test_file, 3=test_name (ADR-091 D2)
                parts = subject.split("::")
                test_name = parts[3] if len(parts) >= 4 else "unknown"
                if test_name == "unknown":
                    # Original was posted as ::unknown when failures were
                    # unparseable. If pytest still reports failure for the
                    # file, the ::unknown subject remains "still failing".
                    failure_current.add(subject)
                elif test_name in failed_test_names:
                    failure_current.add(subject)

        failure_reaudit = await bb_svc.adjudicate_awaiting_reaudit_findings(
            subject_prefix=_FAILURE_REAUDIT_PREFIX,
            current_violation_subjects=failure_current,
            resolved_by="test_runner_sensor",
        )
        failure_released = len(failure_reaudit["released_subjects"])
        failure_resolved = len(failure_reaudit["resolved_subjects"])

        if failure_released or failure_resolved:
            logger.info(
                "TestRunnerSensor: test.runner.failure reaudit drained %d released, %d resolved.",
                failure_released,
                failure_resolved,
            )
            await self.post_report(
                subject="audit.reaudit.complete::test.runner.failure",
                payload={
                    "namespace": "test.runner.failure",
                    "released_count": failure_released,
                    "resolved_count": failure_resolved,
                    "released_subjects": failure_reaudit["released_subjects"],
                    "resolved_subjects": failure_reaudit["resolved_subjects"],
                },
            )
