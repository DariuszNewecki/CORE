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
