from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from will.autonomy.step_zero import find_look_alikes


@pytest.mark.asyncio
# ID: 83e787c5-01f7-4070-aabc-3c07109938ae
async def test_find_look_alikes():
    facts = MagicMock()
    facts.new_public_symbols = {"src/will/app.py": ["my_func"]}

    hit = MagicMock()
    hit.payload = {"file_path": "src/will/other.py", "section": "other_func"}
    hit.score = 0.9876

    qdrant = MagicMock()
    qdrant.collection_name = "code"
    qdrant.search = AsyncMock(return_value=[hit])

    cognitive_service = MagicMock()
    cognitive_service.qdrant_service = qdrant
    cognitive_service.get_embedding_for_code = AsyncMock(return_value=[0.1, 0.2, 0.3])

    with (
        patch(
            "will.autonomy.step_zero.load_test_coverage_config",
            return_value={"test_root": "tests"},
        ),
        patch(
            "will.autonomy.step_zero.added_symbol_source",
            return_value="def my_func(): pass",
        ),
    ):
        result = await find_look_alikes("patch-text", facts, cognitive_service)

    assert result["status"] == "ran"
    assert result["reason"] is None
    assert len(result["symbols"]) == 1
    symbol = result["symbols"][0]
    assert symbol["file"] == "src/will/app.py"
    assert symbol["symbol"] == "my_func"
    assert symbol["matches"] == [
        {"file": "src/will/other.py", "symbol": "other_func", "score": 0.988}
    ]
    cognitive_service.get_embedding_for_code.assert_awaited_once_with(
        "def my_func(): pass"
    )
    qdrant.search.assert_awaited_once()
