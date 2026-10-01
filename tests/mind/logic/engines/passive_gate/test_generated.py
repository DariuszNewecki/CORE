from __future__ import annotations

from unittest.mock import MagicMock

from mind.logic.engines.passive_gate import PassiveGateEngine


# ID: 12489f90-925b-4a20-a293-c938417bf8b3
async def test_PassiveGateEngine_verify_context():
    engine = PassiveGateEngine.__new__(PassiveGateEngine)
    context = MagicMock()
    params = {"key": "value"}

    result = await PassiveGateEngine.verify_context(engine, context, params)

    assert result == []
    assert isinstance(result, list)


import asyncio
from pathlib import Path


# ID: c8c8f449-1a0e-4019-a464-29e2fca94bfa
def test_passive_gate_engine_verify():
    from mind.logic.engines.passive_gate import PassiveGateEngine

    engine = PassiveGateEngine()
    engine_id = getattr(engine, "engine_id", "passive_gate")

    file_path = MagicMock(spec=Path)
    params = {"rule": "some_rule"}

    result = asyncio.run(engine.verify(file_path, params))

    assert result.ok is True
    assert result.violations == []
    assert result.engine_id == engine_id
    assert isinstance(result.message, str)
