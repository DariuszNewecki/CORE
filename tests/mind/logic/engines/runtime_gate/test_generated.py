from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from mind.logic.engines.runtime_gate import RuntimeGateEngine


# ID: 960b0448-d8d1-44e1-8e9c-cca6345c49f3
async def test_RuntimeGateEngine_verify_context() -> None:
    engine = RuntimeGateEngine()
    context = MagicMock()
    params: dict[str, Any] = {"check_type": "worker_process_classification"}

    with patch(
        "mind.logic.engines.runtime_gate._check_worker_process_classification",
        new=AsyncMock(return_value=[]),
    ) as mock_check:
        result = await engine.verify_context(context, params)

    assert result == []
    mock_check.assert_awaited_once_with(context)
