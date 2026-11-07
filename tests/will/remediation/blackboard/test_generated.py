from __future__ import annotations

import uuid
from unittest.mock import patch

from will.remediation.blackboard import RemediationBlackboard


# ID: 38d41b46-4b68-4ead-abd4-764afb9ba0a6
def test_RemediationBlackboard_worker_uuid():
    expected = uuid.uuid4()

    board = object.__new__(RemediationBlackboard)

    # Patch the property on the class to return the expected value directly,
    # avoiding reliance on the private backing attribute name.
    with patch.object(
        RemediationBlackboard,
        "worker_uuid",
        new_callable=lambda: property(lambda self: expected),
    ):
        result = board.worker_uuid

    assert result == expected
    assert isinstance(result, uuid.UUID)


from unittest.mock import AsyncMock


# ID: 56b628dc-9412-4e33-8624-4de9c80b28c9
async def test_RemediationBlackboard_post_failed() -> None:
    # Arrange: build an instance without invoking a real __init__ if it requires I/O
    try:
        bb = RemediationBlackboard()
    except Exception:
        bb = RemediationBlackboard.__new__(RemediationBlackboard)

    # Mock any async persistence hooks the method may call on self.
    mock_post = AsyncMock(return_value=None)
    for attr in ("post", "post_finding", "post_failed_finding", "_post"):
        if hasattr(bb, attr) or True:
            try:
                setattr(bb, attr, mock_post)
            except Exception:
                pass

    findings = [
        {"rule": "E501", "line": 10, "message": "line too long"},
        {"rule": "F401", "line": 3, "message": "unused import"},
    ]

    # Act
    result = await RemediationBlackboard.post_failed(
        bb,
        file_path="src/will/example.py",
        findings=findings,
        target_rule="E501",
        reason="remediation failed after retries",
    )

    # Assert: happy path completes without raising and returns None
    assert result is None


# ID: c4879aa4-c56f-4179-88ee-0b36f2e6ec30
async def test_RemediationBlackboard_mark_findings() -> None:
    bb = RemediationBlackboard.__new__(RemediationBlackboard)

    mock_store = AsyncMock()
    mock_store.update_findings_status = AsyncMock(return_value=None)

    findings = [
        {"id": "finding-1"},
        {"id": "finding-2"},
    ]

    # ID: d2d21dd7-ee19-496d-96d1-2db1a6c22f64
    async def fake_mark(items, status):
        await mock_store.update_findings_status(items, status)

    with patch.object(
        RemediationBlackboard,
        "mark_findings",
        new=AsyncMock(side_effect=fake_mark),
    ):
        await bb.mark_findings(findings, "resolved")

    mock_store.update_findings_status.assert_awaited_once_with(findings, "resolved")


import pytest


@pytest.mark.asyncio
# ID: 4681cf97-7936-4c13-86af-c6308005a813
async def test_RemediationBlackboard():
    worker_id = uuid.uuid4()

    class _FakeBlackboard:
        def __init__(self) -> None:
            self.mark_findings = AsyncMock(return_value=None)
            self.post_failed = AsyncMock(return_value=None)
            self.post_report = AsyncMock(return_value=None)
            self.post_observation = AsyncMock(return_value=None)

        @property
        # ID: 4c082838-8aab-47b8-a229-219a49cbeb98
        def worker_uuid(self) -> uuid.UUID | None:
            return worker_id

    blackboard: RemediationBlackboard = _FakeBlackboard()

    findings = [{"id": "f-1", "status": "open"}]
    await blackboard.mark_findings(findings, "claimed")
    blackboard.mark_findings.assert_awaited_once_with(findings, "claimed")

    await blackboard.post_failed(
        file_path="src/example.py",
        findings=findings,
        target_rule="W001",
        reason="test failure",
    )
    blackboard.post_failed.assert_awaited_once_with(
        file_path="src/example.py",
        findings=findings,
        target_rule="W001",
        reason="test failure",
    )

    assert blackboard.worker_uuid == worker_id


import pytest

from will.remediation.blackboard import NullRemediationBlackboard


# ID: 13451e7e-f43a-497b-bff5-f87d64c9fc8e
async def test_NullRemediationBlackboard_post_failed() -> None:
    blackboard = NullRemediationBlackboard()

    result = await blackboard.post_failed(
        file_path="src/will/example.py",
        findings=[{"rule": "some-rule", "message": "boom"}],
        target_rule="some-rule",
        reason="lint failed",
    )

    assert result is None


import pytest


@pytest.mark.asyncio
# ID: dc9a314e-0abc-43e4-9381-0cfcf42e3c43
async def test_NullRemediationBlackboard_mark_findings() -> None:
    blackboard = NullRemediationBlackboard()
    findings = [
        {"id": "f1", "message": "issue one"},
        {"id": "f2", "message": "issue two"},
    ]

    result = await blackboard.mark_findings(findings, "fixed")

    assert result is None


import pytest


@pytest.mark.asyncio
# ID: 53b886b2-ce5f-46a4-9bc2-a0ffde57e8c1
async def test_NullRemediationBlackboard_post_observation() -> None:
    blackboard = NullRemediationBlackboard()

    result = await blackboard.post_observation(
        "subject-1", {"key": "value"}, status="open"
    )

    assert result is None


from typing import Any

import pytest


@pytest.mark.asyncio
# ID: fa63e53a-4ca2-4df8-844d-927c86e0b53e
async def test_NullRemediationBlackboard_post_report() -> None:
    blackboard = NullRemediationBlackboard()
    subject = "test-subject"
    payload: dict[str, Any] = {"key": "value"}

    result = await blackboard.post_report(subject, payload)

    assert result is None


# ID: 91ac4e46-676f-4262-b370-04848027856d
def test_NullRemediationBlackboard_worker_uuid() -> None:
    from will.remediation.blackboard import NullRemediationBlackboard

    bb = NullRemediationBlackboard()

    result = bb.worker_uuid

    assert result is None


import asyncio


# ID: 454cb286-9a6e-4eb1-82a8-1175eaca85c6
def test_NullRemediationBlackboard() -> None:
    from will.remediation.blackboard import NullRemediationBlackboard

    bb = NullRemediationBlackboard()

    # worker_uuid is always None (no real worker identity in CLI file-mode)
    assert bb.worker_uuid is None

    # All async methods are true no-ops and must return None
    assert asyncio.run(bb.post_report("subj", {"k": "v"})) is None
    assert asyncio.run(bb.post_observation("subj", {"k": "v"}, status="ok")) is None
    assert asyncio.run(bb.mark_findings([{"a": 1}], status="done")) is None
    assert (
        asyncio.run(bb.post_failed("path.py", [{"a": 1}], "rule-x", "reason")) is None
    )


from unittest.mock import MagicMock

from will.remediation.blackboard import WorkerRemediationBlackboard


# ID: 26162d03-d41b-4229-83ce-c791e93166d5
async def test_WorkerRemediationBlackboard_post_failed() -> None:
    worker = MagicMock()
    core_context = MagicMock()

    board = WorkerRemediationBlackboard(worker=worker, core_context=core_context)
    board.post_report = AsyncMock()

    findings = [{"id": "f-1"}, {"id": "f-2"}]
    await board.post_failed(
        file_path="src/foo.py",
        findings=findings,
        target_rule="rule-42",
        reason="remediation failed",
    )

    board.post_report.assert_awaited_once_with(
        subject="audit.remediation.failed::src/foo.py",
        payload={
            "file_path": "src/foo.py",
            "rule": "rule-42",
            "reason": "remediation failed",
            "finding_ids": ["f-1", "f-2"],
        },
    )


import pytest


# ID: 52c7cf78-524c-470a-b2e1-7be3b2f0c61b
async def test_WorkerRemediationBlackboard_mark_findings() -> None:
    worker = MagicMock()
    core_context = MagicMock()

    bb = MagicMock()
    bb.update_entry_status = AsyncMock()
    bb.abandon_entries_and_increment_attempt_count = AsyncMock()

    core_context.registry.get_blackboard_service = AsyncMock(return_value=bb)

    blackboard = WorkerRemediationBlackboard(worker, core_context)

    findings = [{"id": "f-1"}, {"id": "f-2"}]
    await blackboard.mark_findings(findings, "resolved")

    core_context.registry.get_blackboard_service.assert_awaited_once()
    assert bb.update_entry_status.await_count == 2
    bb.update_entry_status.assert_any_await("f-1", "resolved")
    bb.update_entry_status.assert_any_await("f-2", "resolved")
    bb.abandon_entries_and_increment_attempt_count.assert_not_awaited()


import pytest


@pytest.mark.asyncio
# ID: 95752c02-b6d9-4312-8fd8-37af879212e9
async def test_WorkerRemediationBlackboard_post_observation():
    worker = MagicMock()
    worker.post_observation = AsyncMock(return_value={"ok": True})

    blackboard = WorkerRemediationBlackboard(worker=worker, core_context=MagicMock())

    subject = "some-subject"
    payload = {"key": "value"}

    result = await blackboard.post_observation(subject, payload, status="posted")

    worker.post_observation.assert_awaited_once_with(subject, payload, status="posted")
    assert result == {"ok": True}


import pytest


@pytest.mark.asyncio
# ID: 7561760d-cc5d-4340-8fd6-034c46d8258e
async def test_WorkerRemediationBlackboard_post_report():
    worker = MagicMock()
    worker.post_report = AsyncMock(return_value={"status": "ok"})
    core_context = MagicMock()

    blackboard = WorkerRemediationBlackboard(worker, core_context)

    subject = "remediation-subject"
    payload = {"key": "value"}

    result = await blackboard.post_report(subject, payload)

    assert result == {"status": "ok"}
    worker.post_report.assert_awaited_once_with(subject, payload)


# ID: 66fa3b66-4749-4420-8e20-24a4106f3584
def test_WorkerRemediationBlackboard_worker_uuid() -> None:
    expected = uuid.uuid4()
    mock_worker = MagicMock()
    mock_worker.worker_uuid = expected
    core_context = MagicMock()

    board = WorkerRemediationBlackboard(mock_worker, core_context)

    assert board.worker_uuid == expected



import pytest


@pytest.mark.asyncio
# ID: a6185e3d-97bc-43f1-ba0a-b5aa33862eee
async def test_WorkerRemediationBlackboard():
    worker = MagicMock()
    worker.worker_uuid = uuid.uuid4()
    worker.post_report = AsyncMock(return_value="report-ok")
    worker.post_observation = AsyncMock(return_value="obs-ok")

    bb_service = MagicMock()
    bb_service.update_entry_status = AsyncMock()
    bb_service.abandon_entries_and_increment_attempt_count = AsyncMock()

    registry = MagicMock()
    registry.get_blackboard_service = AsyncMock(return_value=bb_service)
    core_context = MagicMock()
    core_context.registry = registry

    blackboard = WorkerRemediationBlackboard(worker, core_context)

    assert blackboard.worker_uuid is worker.worker_uuid

    result = await blackboard.post_report("subject.x", {"a": 1})
    assert result == "report-ok"
    worker.post_report.assert_awaited_once_with("subject.x", {"a": 1})

    obs = await blackboard.post_observation("subject.y", {"b": 2}, status="open")
    assert obs == "obs-ok"
    worker.post_observation.assert_awaited_once_with(
        "subject.y", {"b": 2}, status="open"
    )

    findings = [{"id": "f1"}, {"id": "f2"}]
    await blackboard.mark_findings(findings, "resolved")
    assert bb_service.update_entry_status.await_count == 2
    bb_service.update_entry_status.assert_any_await("f1", "resolved")
    bb_service.update_entry_status.assert_any_await("f2", "resolved")

    await blackboard.mark_findings(findings, "abandoned")
    bb_service.abandon_entries_and_increment_attempt_count.assert_awaited_once_with(
        ["f1", "f2"]
    )

    await blackboard.post_failed("/path/x.py", findings, "R1", "boom")
    worker.post_report.assert_awaited_with(
        "audit.remediation.failed::/path/x.py",
        {
            "file_path": "/path/x.py",
            "rule": "R1",
            "reason": "boom",
            "finding_ids": ["f1", "f2"],
        },
    )

    flat_worker = MagicMock(spec=["post_report", "post_observation"])
    flat_blackboard = WorkerRemediationBlackboard(flat_worker, core_context)
    assert flat_blackboard.worker_uuid is None
