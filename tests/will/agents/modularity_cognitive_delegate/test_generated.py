from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from will.agents.modularity_cognitive_delegate import ModularityCognitiveDelegate


# ID: 5ac3823b-b534-4164-ab43-002e1f7b4de4
async def test_ModularityCognitiveDelegate_execute_cognitive_step():
    core_context = MagicMock()
    delegate = ModularityCognitiveDelegate(core_context)

    expected_result = {"status": "ok", "seams": ["a", "b"]}
    delegate._analyze_modularity_seam = AsyncMock(return_value=expected_result)

    params = {"target": "some.module"}
    result = await delegate.execute_cognitive_step("analyze.modularity_seam", params)

    assert result == expected_result
    delegate._analyze_modularity_seam.assert_awaited_once_with(params)
