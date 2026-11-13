from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mind.logic.engines.schema_gate import SchemaGateEngine


@pytest.mark.asyncio
# ID: 8b6bb077-9638-47aa-a4d1-419f9e13470f
async def test_SchemaGateEngine_evaluate_record():
    engine = MagicMock()

    record = {
        "item-1": {"value": "not-an-integer"},
    }

    params = {
        "schema": {
            "type": "object",
            "properties": {"value": {"type": "integer"}},
        },
        "field": "value",
        "item_types": None,
    }

    mock_part = MagicMock()

    with (
        patch(
            "mind.logic.engines.schema_gate.engine_part", return_value=mock_part
        ) as mock_engine_part,
        patch(
            "mind.logic.engines.schema_gate.record_items",
            return_value=list(record.items()),
        ) as mock_record_items,
    ):
        result = await SchemaGateEngine.evaluate_record(
            engine, record, "my_rule", params
        )

    assert result is mock_part
    mock_engine_part.assert_called_once()
    call_args = mock_engine_part.call_args
    assert call_args.args[1] == "my_rule"
    findings = call_args.args[2]
    assert isinstance(findings, list)
    assert len(findings) == 1
    # schema mismatch is a blocking finding per evaluate_record contract
    assert all(f.blocking for f in findings)
    assert findings[0].item == "item-1"


import asyncio
from pathlib import Path


# ID: 801d1fa7-839d-48c0-a87a-8c7f4552f768
def test_SchemaGateEngine_verify() -> None:
    # Arrange: no external I/O needed; verify() only builds an EngineResult.
    engine = SchemaGateEngine()
    file_path = Path("/tmp/some_record_file.json")
    params: dict = {"any": "param"}

    # Act
    result = asyncio.run(engine.verify(file_path, params))

    # Assert happy path: file is not evaluated — neither pass nor fail
    assert result.ok is True
    assert result.violations == []
    assert result.engine_id == engine.engine_id
    assert "schema_gate" in result.message
    assert "file not evaluated" in result.message
    assert result.extra





# ID: 3eeb6279-1ec1-4577-b9f1-191bd9e30c7e
def test_SchemaGateEngine():
    engine = SchemaGateEngine()

    schema = {
        "type": "object",
        "properties": {"value": {"type": "integer"}},
        "required": ["value"],
    }
    params = {"schema": schema, "field": "value"}
    record = {"item1": {"value": 1}, "item2": {"value": 2}}

    part = asyncio.run(engine.evaluate_record(record, "rule-1", params))

    assert part is not None
    assert list(part.findings) == []
