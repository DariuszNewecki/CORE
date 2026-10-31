from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from will.agents.test_gen_cognitive_delegate import TestGenCognitiveDelegate


# ID: 51072a4d-f2c4-430b-a141-ded3e72f2f84
async def test_TestGenCognitiveDelegate_execute_cognitive_step() -> None:
    core_context = MagicMock()
    delegate = TestGenCognitiveDelegate(core_context)

    expected_result = {"test_code": "def test_sample():\n    assert True\n"}

    with patch.object(
        delegate,
        "_generate_test_snippet",
        new=AsyncMock(return_value=expected_result),
    ) as mock_generate:
        params = {"requirement": "some requirement"}
        result = await delegate.execute_cognitive_step(
            step_ref="generate.test_snippet",
            params=params,
        )

    mock_generate.assert_awaited_once_with(params)
    assert result == expected_result
