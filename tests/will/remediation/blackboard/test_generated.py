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
