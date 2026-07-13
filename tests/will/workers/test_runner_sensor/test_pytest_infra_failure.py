"""TestRunnerSensor.run() must not silently drop its trigger on a
pytest-infra failure (#766, .specs/planning/external-review-2026-07-todo.md
T2.1).

Before the fix, a pytest-infra exception (PathResolver/PytestRunner
construction or run_tests raising) resolved the triggering
python::test.coverage entry unconditionally — the test-gen chain lost its
trigger with no replacement finding posted. The fix leaves the entry open
so the next cycle retries, matching _adjudicate_test_quarantine's existing
"keep subjects in current set to avoid spurious resolve" pattern for the
same failure mode.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from will.workers.test_runner_sensor import TestRunnerSensor


async def test_pytest_infra_failure_does_not_resolve_triggering_entry(
    tmp_path,
) -> None:
    """A PathResolver/PytestRunner construction failure must NOT resolve
    the python::test.coverage entry that triggered this test run."""
    worker = TestRunnerSensor()
    worker.post_heartbeat = AsyncMock()
    worker.post_report = AsyncMock()
    worker.post_artifact_finding = AsyncMock()

    # An existing test file so the "missing" branch isn't taken — the repo's
    # own conftest.py always exists and is unambiguous regardless of cwd.
    existing_test_file = "tests/conftest.py"

    mock_bb_svc = AsyncMock()
    mock_bb_svc.fetch_open_findings.return_value = [
        {
            "id": "entry-1",
            "payload": {"source_file": "src/some/module.py"},
        }
    ]
    mock_bb_svc.fetch_active_finding_subjects_by_prefix.return_value = set()
    mock_bb_svc.adjudicate_awaiting_reaudit_findings.return_value = {
        "released_subjects": [],
        "resolved_subjects": [],
    }
    mock_bb_svc.resolve_entries = AsyncMock()

    with (
        patch("body.services.service_registry.service_registry") as mock_registry,
        patch(
            "will.workers.test_runner_sensor.load_test_coverage_config",
            return_value={},
        ),
        patch(
            "will.workers.test_runner_sensor.uncovered_source_files",
            return_value=set(),
        ),
        patch(
            "will.workers.test_runner_sensor.source_to_test_path",
            return_value=existing_test_file,
        ),
        patch(
            "shared.path_resolver.PathResolver.from_repo",
            side_effect=RuntimeError("pytest-infra unavailable"),
        ),
    ):
        mock_registry.get_blackboard_service = AsyncMock(return_value=mock_bb_svc)
        await worker.run()

    # The infra failure must NOT resolve the triggering entry — leave it
    # open so TestRunnerSensor retries it next cycle.
    mock_bb_svc.resolve_entries.assert_not_awaited()
