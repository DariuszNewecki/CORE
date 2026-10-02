from __future__ import annotations

from pathlib import Path

import pytest

from mind.logic.engines.action_gate import ActionGateEngine


@pytest.mark.asyncio
# ID: 117ee224-7c72-4b9d-b3d0-150a9641c865
async def test_ActionGateEngine_verify():
    engine = ActionGateEngine()
    engine.engine_id = "action_gate"

    params = {
        "attempted_action": "read_data",
        "actions_prohibited": ["delete_data"],
        "actions_allowed": ["read_data", "write_data"],
    }

    result = await engine.verify(Path("/tmp/file.txt"), params)

    assert result.ok is True
    assert "read_data" in result.message
    assert result.violations == []
    assert result.engine_id == "action_gate"


import asyncio


# ID: 098c8ac7-56cc-40a9-98a7-110258f24958
def test_ActionGateEngine() -> None:
    engine = ActionGateEngine()
    params = {
        "attempted_action": "read_file",
        "actions_prohibited": ["schema_migration"],
        "actions_allowed": ["read_file", "write_file"],
    }
    result = asyncio.run(engine.verify(Path("dummy.py"), params))
    assert result.ok is True
    assert result.engine_id == engine.engine_id
    assert result.violations == []
