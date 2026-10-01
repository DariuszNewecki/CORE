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


import pytest


@pytest.mark.asyncio
# ID: aac8976a-c73b-44cf-baa2-73727967f3ff
async def test_WorkflowGateEngine_verify() -> None:
    path_resolver = MagicMock()
    engine = WorkflowGateEngine(path_resolver)

    expected_result = MagicMock()
    engine._verify_async = AsyncMock(return_value=expected_result)

    file_path = Path("src/example.py")
    params = {"key": "value"}

    result = await engine.verify(file_path, params)

    assert result is expected_result
    engine._verify_async.assert_awaited_once_with(file_path, params)


import pytest


@pytest.mark.asyncio
# ID: a0831ace-1258-40bb-8b33-2c97bd47e8f9
async def test_WorkflowGateEngine_verify() -> None:
    path_resolver = MagicMock()
    engine = WorkflowGateEngine(path_resolver)

    file_path = Path("/tmp/some_file.py")
    params: dict[str, Any] = {"some": "param"}
    expected_result = MagicMock(name="EngineResult")

    engine._verify_async = AsyncMock(return_value=expected_result)

    result = await engine.verify(file_path, params)

    engine._verify_async.assert_awaited_once_with(file_path, params)
    assert result is expected_result


import asyncio


# ID: 50c589be-7cde-488c-af3e-6ea0fa95deb3
def test_WorkflowGateEngine_verify_context():
    mock_check = MagicMock()
    mock_check.verify = AsyncMock(return_value=["System violation"])

    mock_path_resolver = MagicMock()

    engine = WorkflowGateEngine(mock_path_resolver)
    engine._checks["test_check"] = mock_check

    context = MagicMock()
    params = {"check_type": "test_check"}

    findings = asyncio.run(engine.verify_context(context, params))

    assert isinstance(findings, list)
    assert len(findings) == 1
    assert findings[0].check_id == "workflow.test_check"
    assert findings[0].message == "System violation"
    assert findings[0].file_path == "System"
    mock_check.verify.assert_awaited_once_with(None, params)


# ID: 123d9d48-3680-45e8-87f3-2bc5861af731
def test_WorkflowGateEngine_verify() -> None:
    import asyncio

    path_resolver = MagicMock()
    engine = WorkflowGateEngine(path_resolver)

    expected_result = MagicMock()
    engine._verify_async = AsyncMock(return_value=expected_result)

    file_path = Path("src/mind/example.py")
    params: dict[str, Any] = {"some": "param"}

    result = asyncio.run(engine.verify(file_path, params))

    assert result is expected_result
    engine._verify_async.assert_awaited_once_with(file_path, params)



from mind.logic.engines.workflow_gate.engine import StructuredViolation


# ID: 837ba6f6-588e-4d8f-8659-ab66378c73d9
async def test_WorkflowGateEngine_verify_context():
    path_resolver = MagicMock()
    engine = WorkflowGateEngine.__new__(WorkflowGateEngine)

    check_logic = MagicMock()
    check_logic.verify = AsyncMock(
        return_value=[
            StructuredViolation(
                message="bad import",
                file_path="src/x.py",
                context={},
            ),
            "some_module.py",
            "plain message",
        ]
    )
    engine._checks = {"my_check": check_logic}

    context = MagicMock()
    params = {"check_type": "my_check"}

    findings = await engine.verify_context(context, params)

    check_logic.verify.assert_awaited_once_with(None, params)
    assert len(findings) == 3

    assert findings[0].check_id == "workflow.my_check"
    assert findings[0].message == "bad import"
    assert findings[0].file_path == "src/x.py"

    assert findings[1].check_id == "workflow.my_check"
    assert findings[1].file_path == "some_module.py"

    assert findings[2].check_id == "workflow.my_check"
    assert findings[2].file_path == "System"
