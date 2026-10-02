from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from mind.logic.engines.grc_judge import GRCJudgeEngine


# ID: d9fec0de-a44e-4cc8-af5d-5b3dbc1292df
def test_GRCJudgeEngine_verify(tmp_path: Path) -> None:
    doc = tmp_path / "doc.txt"
    doc.write_text("This document satisfies the requirement.", encoding="utf-8")

    engine = GRCJudgeEngine.__new__(GRCJudgeEngine)
    engine.engine_id = "grc_judge"
    engine.llm = MagicMock()
    engine._embedder = None
    engine._qdrant = None

    prompt_model = MagicMock()
    prompt_model.invoke = AsyncMock(
        return_value='{"violation": false, "coverage": "satisfied", "reasoning": "met"}'
    )
    engine._prompt_model = prompt_model

    engine._retrieve_source_context = AsyncMock(return_value="")

    params = {
        "instruction": "Does the doc meet the requirement?",
        "rationale": "Control X",
    }

    result = asyncio.run(engine.verify(doc, params))

    assert result.ok is True
    assert result.violations == []
    assert result.engine_id == "grc_judge"
    assert result.extra["coverage"] == "satisfied"
    prompt_model.invoke.assert_awaited_once()
