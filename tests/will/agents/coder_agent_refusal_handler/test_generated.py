from __future__ import annotations

import pytest

from will.agents.coder_agent_refusal_handler import handle_code_generation_result


@pytest.mark.asyncio
# ID: 6fc174f4-9492-4f51-af38-49f5e1623ed8
async def test_handle_code_generation_result():
    expected_code = "def hello():\n    return 'world'"
    result = await handle_code_generation_result(expected_code)
    assert result == expected_code
