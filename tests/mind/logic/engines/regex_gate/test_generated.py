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
    file_path.read_text = MagicMock(return_value=content)

    params = {
        "naming_pattern": r".*\.py$",
        "required_patterns": [r"hello world"],
        "forbidden_patterns": [r"secret_token"],
    }

    with patch("asyncio.to_thread", new=AsyncMock(return_value=content)):
        result = await engine.verify(file_path, params)

    assert result.ok is True
    assert result.violations == []
    assert result.engine_id == "regex_gate"
