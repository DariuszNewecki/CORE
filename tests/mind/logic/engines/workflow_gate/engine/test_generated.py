from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mind.logic.engines.workflow_gate.engine import WorkflowGateEngine


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


import asyncio

import pytest


# ID: 57a74a17-beab-464e-b5c9-b9ee28da3f32
async def test_WorkflowGateEngine_verify_context() -> None:
    path_resolver = MagicMock()
    engine = WorkflowGateEngine(path_resolver)

    check_logic = MagicMock()
    check_logic.verify = AsyncMock(return_value=["some violation", "src/foo.py"])
    engine._checks = {"my_check": check_logic}

    context = MagicMock()
    params = {"check_type": "my_check"}

    findings = await engine.verify_context(context, params)

    check_logic.verify.assert_awaited_once_with(None, params)
    assert len(findings) == 2
    assert findings[0].check_id == "workflow.my_check"
    assert findings[0].message == "some violation"
    assert findings[1].file_path == "src/foo.py"


# ID: 10adbbcc-087f-485d-b050-42e0a71725d2
def test_WorkflowGateEngine_verify() -> None:
    path_resolver = MagicMock()
    engine = WorkflowGateEngine(path_resolver)

    expected = MagicMock(name="EngineResult")
    engine._verify_async = AsyncMock(return_value=expected)

    file_path = Path("src/example.py")
    params = {"foo": "bar"}

    result = asyncio.run(engine.verify(file_path, params))

    assert result is expected
    engine._verify_async.assert_awaited_once_with(file_path, params)
