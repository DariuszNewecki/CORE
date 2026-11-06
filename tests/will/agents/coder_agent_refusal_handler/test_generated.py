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



import pytest


# ID: 98d894df-ea76-4e66-a075-a6fcfa1c0a6e
async def test_CoderAgentRefusalHandler() -> None:
    refusal = MagicMock()
    refusal.component_id = "component-1"
    refusal.phase = MagicMock()
    refusal.phase.value = "implementation"
    refusal.refusal_type = "policy_violation"
    refusal.reason = "Not allowed by policy"
    refusal.suggested_action = "Revise the request"
    refusal.original_request = "please do something"
    refusal.confidence = 0.9
    refusal.data = {"key": "value"}
    refusal.to_user_message.return_value = "Refused: policy_violation"

    handler = CoderAgentRefusalHandler(session_id="sess-1", user_id="user-1")

    mock_repo = MagicMock()
    mock_repo.record_refusal = AsyncMock(return_value=None)
    handler.refusal_repo = mock_repo

    with patch(
        "will.agents.coder_agent_refusal_handler.logger", MagicMock()
    ) as mock_logger:
        with pytest.raises(ValueError, match="Refused: policy_violation"):
            await handler.handle_refusal(refusal)

    mock_repo.record_refusal.assert_awaited_once_with(
        component_id="component-1",
        phase="implementation",
        refusal_type="policy_violation",
        reason="Not allowed by policy",
        suggested_action="Revise the request",
        original_request="please do something",
        confidence=0.9,
        context_data={"key": "value"},
        session_id="sess-1",
        user_id="user-1",
    )
    assert mock_logger.warning.called
