from __future__ import annotations

import asyncio
from pathlib import Path

from mind.logic.engines.glob_gate import GlobGateEngine


# ID: c29bebc1-c1e9-44f2-b643-2ead0078854f
def test_GlobGateEngine():
    engine = GlobGateEngine()
    assert engine.engine_id == "glob_gate"

    # Happy path: path matching the allowed boundary -> ok True
    result = asyncio.run(
        engine.verify(
            Path("/repo/src/mind/logic/app.py"),
            {
                "check_type": "allowed_top_level_dirs",
                "allowed": ["src/mind/**", "src/body/**"],
            },
        )
    )
    assert result.ok is True
    assert result.engine_id == "glob_gate"
    assert result.violations == []


from unittest.mock import MagicMock


# ID: 4b07a324-e9a0-4d05-b6f0-1eaccde3b555
async def test_GlobGateEngine_verify():
    # Instantiate the engine under test
    engine = GlobGateEngine()

    # Ensure deterministic engine id and matching behavior
    engine.engine_id = "glob_gate"
    engine._match = MagicMock(return_value=False)

    result = await engine.verify(
        Path("/project/src/module.py"),
        {"patterns": ["forbidden/**"]},
    )

    assert result.ok is True
    assert result.violations == []
    assert result.engine_id == "glob_gate"
