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
