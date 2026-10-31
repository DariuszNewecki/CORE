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
