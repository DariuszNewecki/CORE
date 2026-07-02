# tests/will/workers/audit_violation_sensor/test_no_data_guard.py
"""Unit tests for AuditViolationSensor ADR-137 D1 no-data guard (P1-B sweep f3fc59b5).

When the artifact glob walk returns an empty file universe (file_count == 0),
the sensor MUST post an `audit_violation_sensor.no_data` report and return
without proceeding to rule resolution. This is the "frozen-flow" principle
operationalized at the sensor level — distinguishable from a clean pass.

Tests use the real AuditViolationSensor class (real declaration load) and
patch the I/O boundary: blackboard posting and intent/context dependencies.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from will.workers.audit_violation_sensor import AuditViolationSensor


def _build_mock_intent_repo(artifact_globs: list[str]) -> MagicMock:
    """Return a mock IntentRepository whose get_artifact_type returns the given globs."""
    artifact_type = MagicMock()
    artifact_type.content = {"discovery": artifact_globs}
    mock_repo = MagicMock()
    mock_repo.get_artifact_type.return_value = artifact_type
    mock_repo._rule_index = {}
    return mock_repo


def _build_mock_auditor_context(repo_path: Path) -> MagicMock:
    ctx = MagicMock()
    ctx.repo_path = repo_path
    ctx.reload_governance.return_value = None
    ctx.invalidate_file_cache.return_value = None
    return ctx


def _make_sensor() -> AuditViolationSensor:
    """Construct a real AuditViolationSensor (loads real declaration from disk)."""
    core_context = MagicMock()
    return AuditViolationSensor(
        core_context=core_context,
        declaration_name="audit_violation_sensor",
        rule_namespace="test_ns",
    )


async def test_no_data_guard_fires_when_file_count_is_zero(tmp_path: Path) -> None:
    """file_count == 0 → post no_data report, do NOT proceed to rule resolution."""
    sensor = _make_sensor()

    mock_repo = _build_mock_intent_repo(["**/*.nonexistent_xyz"])
    mock_auditor_ctx = _build_mock_auditor_context(tmp_path)
    sensor._core_context.auditor_context = mock_auditor_ctx

    posted_reports: list[dict] = []

    async def capture_post_report(subject: str, payload: dict) -> None:
        posted_reports.append({"subject": subject, "payload": payload})

    sensor.post_heartbeat = AsyncMock()
    sensor.post_report = capture_post_report  # type: ignore[method-assign]

    with patch(
        "will.workers.audit_violation_sensor.get_intent_repository",
        return_value=mock_repo,
    ):
        await sensor.run()

    assert len(posted_reports) == 1, "Expected exactly one post_report call"
    assert posted_reports[0]["subject"] == "audit_violation_sensor.no_data"
    payload = posted_reports[0]["payload"]
    assert payload["file_count"] == 0
    assert payload["rule_namespace"] == "test_ns"
    assert "artifact_type" in payload


async def test_no_data_guard_does_not_post_run_complete(tmp_path: Path) -> None:
    """When the guard fires, `audit_violation_sensor.run.complete` must NOT be posted."""
    sensor = _make_sensor()

    mock_repo = _build_mock_intent_repo(["**/*.nonexistent_xyz"])
    mock_auditor_ctx = _build_mock_auditor_context(tmp_path)
    sensor._core_context.auditor_context = mock_auditor_ctx

    subjects_posted: list[str] = []

    async def capture_subject(subject: str, payload: dict) -> None:
        subjects_posted.append(subject)

    sensor.post_heartbeat = AsyncMock()
    sensor.post_report = capture_subject  # type: ignore[method-assign]

    with patch(
        "will.workers.audit_violation_sensor.get_intent_repository",
        return_value=mock_repo,
    ):
        await sensor.run()

    assert "audit_violation_sensor.run.complete" not in subjects_posted


async def test_no_data_guard_bypassed_when_files_exist(tmp_path: Path) -> None:
    """When at least one file matches the glob, the no-data guard does not fire.

    We verify by checking that `audit_violation_sensor.no_data` is NOT among
    the posted subjects. The run() call may produce other reports (e.g.
    run.complete when no rules resolve) — that is expected and fine.
    """
    # Create one real .py file so glob("**/*.py") finds it
    (tmp_path / "example.py").write_text("x = 1\n", encoding="utf-8")

    sensor = _make_sensor()
    mock_repo = _build_mock_intent_repo(["**/*.py"])
    mock_repo._rule_index = {}
    mock_auditor_ctx = _build_mock_auditor_context(tmp_path)
    sensor._core_context.auditor_context = mock_auditor_ctx

    subjects_posted: list[str] = []

    async def capture_subject(subject: str, payload: dict) -> None:
        subjects_posted.append(subject)

    sensor.post_heartbeat = AsyncMock()
    sensor.post_report = capture_subject  # type: ignore[method-assign]

    # _resolve_rule_ids will be called — short-circuit it to return empty list
    # so run() posts run.complete instead of going further into the audit loop.
    with (
        patch(
            "will.workers.audit_violation_sensor.get_intent_repository",
            return_value=mock_repo,
        ),
        patch.object(sensor, "_resolve_rule_ids", return_value=[]),
    ):
        await sensor.run()

    assert "audit_violation_sensor.no_data" not in subjects_posted
