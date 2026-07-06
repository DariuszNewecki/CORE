from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from will.workers.violation_remediator_body.ceremony import CeremonyMixin


# ID: 91c87a42-fc5f-42fc-995a-7515d01ed5f9
class ConcreteCeremonyMixin(CeremonyMixin):
    """Concrete subclass to test the mixin."""

    def __init__(self):
        self._ctx = MagicMock()
        self._target_rule = "test-rule"


@pytest.mark.asyncio
# ID: 80a3a112-2369-4c2d-abf2-5c5855f530d3
async def test_CeremonyMixin():
    mixin = ConcreteCeremonyMixin()
    mock_action_executor = AsyncMock()
    mock_action_executor.execute.return_value = MagicMock(
        ok=True, data={"crate_id": "crate-123"}
    )
    mixin._ctx.action_executor = mock_action_executor

    # _pack_crate happy path
    result = await mixin._pack_crate("test.py", "fixed source")
    assert result == "crate-123"
    mock_action_executor.execute.assert_awaited_once_with(
        "crate.create",
        write=True,
        intent="Fix test-rule violations in test.py via autonomous remediation",
        payload_files={"test.py": "fixed source"},
    )
