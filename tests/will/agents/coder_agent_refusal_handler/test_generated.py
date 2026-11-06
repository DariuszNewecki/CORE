from __future__ import annotations

import pytest

from will.agents.coder_agent_refusal_handler import handle_code_generation_result


@pytest.mark.asyncio
# ID: 6fc174f4-9492-4f51-af38-49f5e1623ed8
async def test_handle_code_generation_result():
    expected_code = "def hello():\n    return 'world'"
    result = await handle_code_generation_result(expected_code)
    assert result == expected_code


from unittest.mock import AsyncMock, MagicMock, patch

from will.agents.coder_agent_refusal_handler import CoderAgentRefusalHandler


# ID: ad9664fb-717d-458e-af2a-b85648a0e247
async def test_CoderAgentRefusalHandler_handle_refusal():
    refusal = MagicMock()
    refusal.to_user_message = MagicMock(return_value="refused")

    with patch(
        "will.agents.coder_agent_refusal_handler.RefusalRepository", MagicMock()
    ):
        handler = CoderAgentRefusalHandler(session_id="sid", user_id="uid")

    handler._record_refusal = AsyncMock()
    handler._log_refusal = MagicMock()

    import pytest

    with pytest.raises(ValueError, match="refused"):
        await handler.handle_refusal(refusal)

    handler._record_refusal.assert_awaited_once_with(refusal)
    handler._log_refusal.assert_called_once_with(refusal)
    refusal.to_user_message.assert_called_once()
