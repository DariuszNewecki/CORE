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


from unittest.mock import patch


# ID: b0adc47d-2f7e-4d23-adaf-4dd0d7216f2a
def test_GRCJudgeEngine(tmp_path: Path) -> None:
    prompt_model = MagicMock()
    prompt_model.invoke = AsyncMock(
        return_value='{"violation": false, "coverage": "satisfied", "reasoning": "ok"}'
    )

    path_resolver = MagicMock()
    llm_client = MagicMock()

    with patch(
        "mind.logic.engines.grc_judge.PromptModel.load",
        return_value=prompt_model,
    ):
        engine = GRCJudgeEngine(path_resolver, llm_client)

    doc = tmp_path / "doc.txt"
    doc.write_text("Some compliance document content.", encoding="utf-8")

    result = asyncio.run(
        engine.verify(
            doc,
            {
                "instruction": "Does the document establish access control?",
                "rationale": "Control AC-1",
            },
        )
    )

    assert result.ok is True
    assert result.violations == []
    assert result.engine_id == "grc_judge"
    assert result.extra.get("coverage") == "satisfied"

    prompt_model.invoke.assert_awaited_once()
    call_kwargs = prompt_model.invoke.await_args.kwargs
    assert call_kwargs["context"]["instruction"] == (
        "Does the document establish access control?"
    )
    assert call_kwargs["context"]["content"] == "Some compliance document content."
    assert call_kwargs["client"] is llm_client
