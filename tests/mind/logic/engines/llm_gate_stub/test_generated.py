from __future__ import annotations

import asyncio
from pathlib import Path

from mind.logic.engines.llm_gate_stub import LLMGateStubEngine


# ID: d9a0b9f3-2c04-4bf2-bd28-9e7e22db666a
def test_LLMGateStubEngine_verify():
    engine = LLMGateStubEngine()

    file_path = Path("example.py")
    params = {"instruction": "Check for security issues"}

    result = asyncio.run(engine.verify(file_path, params))

    assert result.ok is True
    assert result.message == "LLM check skipped (stub mode - no API call)"
    assert result.violations == []
    assert result.engine_id == engine.engine_id


# ID: 34b78713-c945-4791-92a3-115e3a75617e
def test_LLMGateStubEngine():
    engine = LLMGateStubEngine()

    result = asyncio.run(
        engine.verify(Path("/tmp/example.py"), {"instruction": "check something"})
    )

    assert result.ok is True
    assert result.violations == []
    assert result.engine_id == "llm_gate_stub"
    assert "stub mode" in result.message
