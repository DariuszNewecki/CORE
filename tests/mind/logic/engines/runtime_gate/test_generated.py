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


from pathlib import Path


# ID: e992534c-06de-4f85-8fad-903ab70050d0
async def test_RuntimeGateEngine():
    engine = RuntimeGateEngine()

    # Happy path 1: per-file dispatch is a contract violation.
    result = await engine.verify(
        Path("foo.py"), {"check_type": "worker_process_classification"}
    )
    assert result.ok is False
    assert "context-level only" in result.message
    assert result.engine_id == engine.engine_id
    assert len(result.violations) == 1

    # Happy path 2: verify_context dispatches to the registered check.
    sentinel = [MagicMock()]
    with patch(
        "mind.logic.engines.runtime_gate._check_worker_process_classification",
        new=AsyncMock(return_value=sentinel),
    ) as mock_check:
        context = MagicMock()
        findings = await engine.verify_context(
            context, {"check_type": "worker_process_classification"}
        )
        mock_check.assert_awaited_once_with(context)
        assert findings is sentinel

    # Happy path 3: unsupported check_type surfaces a HIGH finding.
    with patch(
        "mind.logic.engines.runtime_gate._check_worker_process_classification",
        new=AsyncMock(),
    ) as mock_check:
        findings = await engine.verify_context(MagicMock(), {"check_type": "nope"})
        mock_check.assert_not_awaited()
        assert len(findings) == 1
        assert "unsupported" in findings[0].message
