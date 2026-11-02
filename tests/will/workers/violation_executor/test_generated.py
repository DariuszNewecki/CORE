from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
# ID: f50e8ea1-6cf4-4043-80ee-8f4b0b0a2570
async def test_ViolationExecutorWorker_run() -> None:
    from will.remediation import finding_state as real_finding_state
    from will.workers.violation_executor import ViolationExecutorWorker

    worker = ViolationExecutorWorker.__new__(ViolationExecutorWorker)
    worker._worker_uuid = "worker-123"
    worker._files_per_cycle_max = 10
    worker.post_heartbeat = AsyncMock()
    worker.post_report = AsyncMock()
    worker._process_file = AsyncMock(return_value=(True, ["rule-1"]))
    worker._surface_candidate = AsyncMock()
    worker._post_blast_bound_finding = AsyncMock()
    worker._load_mapped_rule_ids = MagicMock(return_value={"rule-x"})

    findings = [
        {"id": "f1", "payload": {"file_path": "/tmp/a.py", "rule_id": "rule-1"}},
    ]

    claim_mock = AsyncMock(return_value=findings)
    attempt_mock = AsyncMock(return_value=0)
    release_mock = AsyncMock()
    delegate_mock = AsyncMock()

    cfg = MagicMock()
    cfg.workers.violation_executor.claim_limit = 50
    cfg.blackboard.remediation_cap_n = 100

    with (
        patch.object(real_finding_state, "claim_unmapped_findings", claim_mock),
        patch.object(real_finding_state, "query_file_attempt_count", attempt_mock),
        patch.object(real_finding_state, "release_findings", release_mock),
        patch.object(real_finding_state, "delegate_capped_findings", delegate_mock),
        patch(
            "will.workers.violation_executor.load_operational_config",
            return_value=cfg,
        ),
        patch(
            "will.workers.violation_executor.asyncio.to_thread",
            new=AsyncMock(return_value={"rule-x"}),
        ),
    ):
        await worker.run()

    worker.post_heartbeat.assert_awaited_once()
    claim_mock.assert_awaited_once()
    _, claim_kwargs = claim_mock.call_args
    assert claim_kwargs["claimed_by"] == "worker-123"
    assert claim_kwargs["limit"] == 50
    worker._process_file.assert_awaited_once()
    worker._surface_candidate.assert_awaited_once_with("rule-1", "/tmp/a.py")
    worker.post_report.assert_awaited_once()
    _, kwargs = worker.post_report.call_args
    payload = kwargs["payload"]
    assert payload["claimed"] == 1
    assert payload["succeeded"] == 1
    assert payload["failed"] == 0
    assert payload["candidates_surfaced"] == 1



from will.workers.violation_executor import ViolationExecutorWorker


# ID: 2fee95c0-848a-417f-8397-5f944debccb1
def test_ViolationExecutorWorker() -> None:
    core_context = MagicMock()
    worker = ViolationExecutorWorker(core_context)
    assert worker._ctx is core_context
    assert worker.declaration_name == "violation_executor"
    assert isinstance(worker._files_per_cycle_max, int)
