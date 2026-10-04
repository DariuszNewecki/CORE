from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from will.workers.violation_remediator_body.worker import ViolationRemediator


# ID: 0ea9d8ee-3a70-4968-a490-3b77c39ac598
def test_ViolationRemediator_run() -> None:
    import asyncio

    ctx = MagicMock()
    worker = ViolationRemediator(ctx, target_rule="some-rule")

    findings = [
        {"id": 1, "payload": {"file_path": "a.py"}},
        {"id": 2, "payload": {"file_path": "b.py"}},
        {"id": 3, "payload": {"file_path": "a.py"}},
    ]

    worker.post_heartbeat = AsyncMock()
    worker.post_report = AsyncMock()
    worker._claim_open_findings = AsyncMock(return_value=findings)

    mock_ceremony = MagicMock()
    mock_ceremony.process_file = AsyncMock(return_value=True)

    with (
        patch(
            "will.workers.violation_remediator_body.worker.RemediationCeremony",
            return_value=mock_ceremony,
        ),
        patch(
            "will.workers.violation_remediator_body.worker.WorkerRemediationBlackboard",
        ),
    ):
        asyncio.run(worker.run())

    worker.post_heartbeat.assert_awaited_once()
    worker._claim_open_findings.assert_awaited_once()
    assert mock_ceremony.process_file.await_count == 2
    worker.post_report.assert_awaited_once()
    call_kwargs = worker.post_report.await_args.kwargs
    assert call_kwargs["subject"] == "violation_remediator.run.complete"
    assert call_kwargs["payload"]["succeeded"] == 2
    assert call_kwargs["payload"]["failed"] == 0
