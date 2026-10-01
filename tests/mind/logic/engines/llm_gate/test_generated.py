from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from mind.logic.engines.llm_gate import LLMGateEngine


# ID: d5e9cddc-425f-4b57-bbfe-d9a8fb02de52
def test_LLMGateEngine_verify(tmp_path: Path) -> None:
    target = tmp_path / "sample.py"
    target.write_text("print('hello')\n", encoding="utf-8")

    path_resolver = MagicMock()
    path_resolver.repo_root = tmp_path

    llm_client = MagicMock()

    engine = LLMGateEngine(path_resolver=path_resolver, llm_client=llm_client)
    engine.engine_id = "llm_gate"

    engine._audit_prompt_model = MagicMock()
    engine._audit_prompt_model.invoke = AsyncMock(
        return_value=json.dumps({"violation": False})
    )

    params: dict = {"instruction": "Be nice", "rationale": "Because."}

    result = asyncio.run(engine.verify(file_path=target, params=params))

    assert result.ok is True
    assert result.violations == []
    assert result.engine_id == "llm_gate"
    engine._audit_prompt_model.invoke.assert_awaited_once()
