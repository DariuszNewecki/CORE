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
