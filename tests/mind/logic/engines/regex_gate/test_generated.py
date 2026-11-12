from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mind.logic.engines.regex_gate import RegexGateEngine


@pytest.mark.asyncio
# ID: 89c3ce3c-7c08-47f0-b727-04b4db56e7cf
async def test_RegexGateEngine_verify() -> None:
    engine = RegexGateEngine()
    engine.engine_id = "regex_gate"

    file_path = MagicMock(spec=Path)
    file_path.name = "compliant_file.py"

    content = "line one\nline two\nhello world\n"
    file_path.read_bytes = MagicMock(return_value=content.encode("utf-8"))

    params = {
        "naming_pattern": r".*\.py$",
        "required_patterns": [r"hello world"],
        "forbidden_patterns": [r"secret_token"],
    }

    with patch(
        "asyncio.to_thread", new=AsyncMock(return_value=content.encode("utf-8"))
    ):
        result = await engine.verify(file_path, params)

    assert result.ok is True
    assert result.violations == []
    assert result.engine_id == "regex_gate"


import asyncio


# ID: def93730-5b34-472b-9ffd-2976d70e786c
def test_RegexGateEngine():
    async def _run():
        engine = RegexGateEngine()
        target = MagicMock()
        target.name = "good_name.py"
        target.read_bytes = MagicMock(
            return_value=b"import os\n# header\nprint('ok')\n"
        )

        params = {
            "naming_pattern": r"^good_name\.py$",
            "required_patterns": [r"import os"],
            "forbidden_patterns": [r"SECRET_KEY"],
        }

        result = await engine.verify(target, params)

        assert result.ok is True
        assert result.violations == []
        assert result.engine_id == "regex_gate"

    asyncio.run(_run())





# ID: 72598bea-b06b-4eab-856f-f13f235f9310
async def test_RegexGateEngine_evaluate_record():
    engine = RegexGateEngine()

    record = {
        "items": [
            {"id": "i1", "value": "contains FORBIDDEN token"},
            {"id": "i2", "value": "clean value"},
            {"id": "i3", "value": "needs required token here"},
            {"id": "i4", "value": 12345},
        ]
    }
    params = {
        "field": "value",
        "forbidden_patterns": [r"FORBIDDEN"],
        "required_patterns": [r"required"],
    }

    with (
        patch(
            "mind.logic.engines.regex_gate.record_items",
            return_value=[
                ("i1", {"id": "i1", "value": "contains FORBIDDEN token"}),
                ("i2", {"id": "i2", "value": "clean value"}),
                ("i3", {"id": "i3", "value": "needs required token here"}),
                ("i4", {"id": "i4", "value": 12345}),
            ],
        ) as mock_record_items,
        patch("mind.logic.engines.regex_gate.engine_part") as mock_engine_part,
    ):
        mock_engine_part.return_value = MagicMock(name="RulePart")

        result = await engine.evaluate_record(record, "rule-1", params)

    assert result is mock_engine_part.return_value
    mock_record_items.assert_called_once_with(record, None)

    mock_engine_part.assert_called_once()
    call_args = mock_engine_part.call_args
    assert call_args.args[0] is engine
    assert call_args.args[1] == "rule-1"

    findings = call_args.args[2]
    assert isinstance(findings, list)
    # i1 -> forbidden + required missing; i2 -> required missing; i3 -> has required
    assert len(findings) == 3
    assert all(f.rule == "rule-1" for f in findings)
    assert all(f.blocking is True for f in findings)

    items = {f.item for f in findings}
    assert items == {"i1", "i2"}

    for f in findings:
        assert f.message.startswith(f"{f.item}.value: ")
