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
