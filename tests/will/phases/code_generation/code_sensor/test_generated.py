from __future__ import annotations

from unittest.mock import MagicMock

from will.phases.code_generation.code_sensor import CodeSensor


# ID: 52cf47ac-e15f-4071-914b-8a628ae147b0
async def test_CodeSensor_sense_artifact():
    execution_sensor = MagicMock()
    sensor = CodeSensor(execution_sensor=execution_sensor)

    sensor._validate_syntax = MagicMock(return_value=(True, None))
    sensor._is_test_file = MagicMock(return_value=False)

    passed, error = await sensor.sense_artifact(
        file_path="src/example_module.py",
        code="def foo():\n    return 42\n",
    )

    assert passed is True
    assert error is None


from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
# ID: 92c14ea3-555a-4ba0-bc9c-b7914c1d053a
async def test_CodeSensor_sense():
    execution_sensor = MagicMock()
    sensor = CodeSensor(execution_sensor)
    sensor.sense_artifact = AsyncMock(return_value=(True, None))

    result = await sensor.sense("print('hi')", "src/foo.py")

    sensor.sense_artifact.assert_awaited_once_with("src/foo.py", "print('hi')")
    assert result["status"] == "sensed"
    assert result["passed"] is True
    assert result["error"] is None
    assert result["issues"] == []
    assert result["quality_score"] == 0.92
    assert result["suggestions"] == []
    assert result["metadata"]["file"] == "src/foo.py"
    assert result["metadata"]["validation_mode"] == "structural+functional"
    assert result["metadata"]["workspace_provided"] is False


import pytest


@pytest.mark.asyncio
# ID: bc6ca3cc-e2b4-4067-8b50-2f27d3cdf215
async def test_CodeSensor():
    execution_sensor = MagicMock()
    sensor = CodeSensor(execution_sensor)

    valid_code = "def foo():\n    return 42\n"
    result = await sensor.sense(valid_code, "module.py")

    assert result["status"] == "sensed"
    assert result["passed"] is True
    assert result["error"] is None
    assert result["issues"] == []
    assert result["quality_score"] == 0.92
    assert result["suggestions"] == []
    assert result["metadata"]["file"] == "module.py"
    assert result["metadata"]["validation_mode"] == "structural+functional"
    assert result["metadata"]["workspace_provided"] is False
