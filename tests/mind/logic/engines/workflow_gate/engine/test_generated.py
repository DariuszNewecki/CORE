from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from mind.logic.engines.workflow_gate.engine import WorkflowGateEngine


@pytest.mark.asyncio
# ID: 9064e5e7-77ed-4180-aaf0-cf4d35dcbf02
async def test_WorkflowGateEngine_verify() -> None:
    path_resolver = MagicMock()
    engine = WorkflowGateEngine(path_resolver)

    expected_result = MagicMock()
    engine._verify_async = AsyncMock(return_value=expected_result)

    file_path = Path("src/example.py")
    params: dict[str, Any] = {"some": "param"}

    result = await engine.verify(file_path, params)

    assert result is expected_result
    engine._verify_async.assert_awaited_once_with(file_path, params)


import pytest


@pytest.mark.asyncio
# ID: 433a36b2-2d7c-4eef-a66e-579303c98a5b
async def test_WorkflowGateEngine_verify_context() -> None:
    engine = WorkflowGateEngine.__new__(WorkflowGateEngine)
    engine._checks = {}

    mock_check = MagicMock()
    mock_check.verify = AsyncMock(return_value=["src/foo.py"])
    engine._checks["my_check"] = mock_check

    context = MagicMock()
    params = {"check_type": "my_check"}

    findings = await engine.verify_context(context, params)

    mock_check.verify.assert_awaited_once_with(None, params)
    assert len(findings) == 1
    assert findings[0].check_id == "workflow.my_check"
    assert findings[0].file_path == "src/foo.py"


from unittest.mock import patch

import pytest


@pytest.mark.asyncio
# ID: 40806231-7628-46eb-9179-185e232a82fb
async def test_WorkflowGateEngine() -> None:
    path_resolver = MagicMock()

    with patch(
        "mind.logic.engines.workflow_gate.engine.TestVerificationCheck"
    ) as mock_check_cls:
        mock_check = MagicMock()
        mock_check.check_type = "test_verification"
        mock_check.verify = AsyncMock(return_value=[])
        mock_check_cls.return_value = mock_check

        engine = WorkflowGateEngine(path_resolver)

        assert engine.engine_id == "workflow_gate"
        assert "test_verification" in engine._checks

        result = await engine.verify(
            Path("some_file.py"), {"check_type": "test_verification"}
        )

        assert result.ok is True
        assert result.engine_id == "workflow_gate"
        assert result.violations == []
        mock_check.verify.assert_awaited_once()
