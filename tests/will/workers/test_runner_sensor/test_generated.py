from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from will.workers.test_runner_sensor import TestRunnerSensor


@pytest.mark.asyncio
# ID: c3bfda65-af8b-4d7f-ae7f-b8a476232309
async def test_TestRunnerSensor():
    worker = TestRunnerSensor()

    # Mock dependencies
    mock_bb_svc = AsyncMock()
    mock_bb_svc.fetch_open_findings.return_value = []
    mock_bb_svc.fetch_active_finding_subjects_by_prefix.return_value = set()
    mock_bb_svc.adjudicate_awaiting_reaudit_findings.return_value = {
        "released_subjects": [],
        "resolved_subjects": [],
    }

    mock_config = {}

    # Patch service_registry and config loader
    with patch("body.services.service_registry.service_registry") as mock_registry:
        mock_registry.get_blackboard_service = AsyncMock(return_value=mock_bb_svc)

        with patch(
            "will.workers.test_runner_sensor.load_test_coverage_config",
            return_value=mock_config,
        ):
            with patch(
                "will.workers.test_runner_sensor.uncovered_source_files",
                return_value=set(),
            ):
                # Mock heartbeat, report, and artifact_finding posting
                worker.post_heartbeat = AsyncMock()
                worker.post_report = AsyncMock()
                worker.post_artifact_finding = AsyncMock()

                await worker.run()

    # Verify happy path: no findings to process
    worker.post_heartbeat.assert_awaited_once()
    mock_bb_svc.fetch_open_findings.assert_awaited_once_with(
        prefix="python::test.coverage::%", limit=50
    )
    worker.post_report.assert_awaited_once_with(
        subject="test_runner_sensor.run.complete",
        payload={"message": "No test.coverage findings to process."},
    )


# ID: bfb4a7fe-a350-42b4-951c-7163f4d1f8b4
async def test_TestRunnerSensor_run(tmp_path):
    """One cycle over every branch of the queue loop.

    - no source_file / unmappable source_file: entry resolved, nothing posted
    - test file absent: test.runner.missing posted (unless already open)
    - pytest fails with FAILED lines: one test.runner.failure per test
    - pytest fails without FAILED lines: one ::unknown failure
    - pytest passes but public symbols are untested: test.runner.missing
    Every entry is resolved, the quarantine drain runs with the same config,
    and the report carries the counts.
    """
    worker = TestRunnerSensor()
    worker._repo_root = tmp_path
    worker.post_heartbeat = AsyncMock()
    worker.post_report = AsyncMock()
    worker.post_artifact_finding = AsyncMock()
    worker._adjudicate_test_quarantine = AsyncMock()

    for name in ("failing", "unknown", "passing"):
        test_file = tmp_path / "tests" / "a" / name / "test_generated.py"
        test_file.parent.mkdir(parents=True)
        test_file.write_text("", encoding="utf-8")

    findings = [
        {"id": "e-empty", "payload": {}},
        {"id": "e-bad", "payload": {"source_file": "lib/outside.py"}},
        {"id": "e-missing", "payload": {"source_file": "src/a/missing.py"}},
        {"id": "e-dup", "payload": {"source_file": "src/a/dup.py"}},
        {"id": "e-fail", "payload": {"source_file": "src/a/failing.py"}},
        {"id": "e-unknown", "payload": {"source_file": "src/a/unknown.py"}},
        {"id": "e-pass", "payload": {"source_file": "src/a/passing.py"}},
    ]
    failing_output = (
        "FAILED tests/a/failing/test_generated.py::test_one - assert 1\n"
        "FAILED tests/a/failing/test_generated.py::test_two - assert 2\n"
    )
    results = {
        "tests/a/failing/test_generated.py": {
            "exit_code": 1,
            "output": failing_output,
        },
        "tests/a/unknown/test_generated.py": {
            "exit_code": 2,
            "output": "ERROR collecting",
        },
        "tests/a/passing/test_generated.py": {
            "exit_code": 0,
            "passed": 3,
            "output": "3 passed",
        },
    }

    async def _run_tests(paths):
        return results[paths[0]]

    runner = AsyncMock()
    runner.run_tests = AsyncMock(side_effect=_run_tests)

    bb_svc = AsyncMock()
    bb_svc.fetch_open_findings.return_value = findings
    bb_svc.fetch_active_finding_subjects_by_prefix.return_value = {
        "python::test.runner.missing::src/a/dup.py"
    }
    config = {
        "source_root": "src",
        "test_root": "tests",
        "test_file_suffix": "/test_generated.py",
    }

    with (
        patch("body.services.service_registry.service_registry") as registry,
        patch(
            "will.workers.test_runner_sensor.load_test_coverage_config",
            return_value=config,
        ),
        patch("will.workers.test_runner_sensor.intent_root_for"),
        patch("shared.path_resolver.PathResolver.from_repo"),
        patch("will.phases.canary.pytest_runner.PytestRunner", return_value=runner),
        patch(
            "will.workers.test_runner_sensor.has_untested_public_symbols",
            return_value=True,
        ) as untested,
    ):
        registry.get_blackboard_service = AsyncMock(return_value=bb_svc)
        await worker.run()

    resolved = [c.args[0] for c in bb_svc.resolve_entries.await_args_list]
    assert resolved == [[f["id"]] for f in findings]

    assert [c.args[0] for c in runner.run_tests.await_args_list] == [
        ["tests/a/failing/test_generated.py"],
        ["tests/a/unknown/test_generated.py"],
        ["tests/a/passing/test_generated.py"],
    ]
    untested.assert_called_once_with(
        tmp_path / "src/a/passing.py",
        tmp_path / "tests/a/passing/test_generated.py",
    )

    posted = [
        (c.kwargs["sub_namespace"], c.kwargs["identity_key_value"])
        for c in worker.post_artifact_finding.await_args_list
    ]
    assert posted == [
        ("test.runner.missing", "src/a/missing.py"),
        (
            "test.runner.failure",
            "tests/a/failing/test_generated.py::"
            "tests/a/failing/test_generated.py::test_one",
        ),
        (
            "test.runner.failure",
            "tests/a/failing/test_generated.py::"
            "tests/a/failing/test_generated.py::test_two",
        ),
        ("test.runner.failure", "tests/a/unknown/test_generated.py::unknown"),
        ("test.runner.missing", "src/a/passing.py"),
    ]
    first_failure = worker.post_artifact_finding.await_args_list[1].kwargs
    assert first_failure["artifact_type"] == "python"
    assert first_failure["payload"]["source_file"] == "src/a/failing.py"
    assert first_failure["payload"]["output"] == failing_output

    worker._adjudicate_test_quarantine.assert_awaited_once_with(config)
    worker.post_report.assert_awaited_once_with(
        subject="test_runner_sensor.run.complete",
        payload={"run": 3, "passed": 3, "failed": 3, "missing": 3},
    )
