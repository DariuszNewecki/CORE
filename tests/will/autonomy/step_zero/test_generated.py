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


import asyncio
from types import SimpleNamespace

from will.autonomy.step_zero import build_step_zero_report


# ID: 5eaacfd8-624c-41cc-8a68-cc7e44b6da33
def test_build_step_zero_report(tmp_path):
    patch_arg = "diff --git a/x b/x"
    retires = ["ADR-001"]
    repo_root = tmp_path

    facts = SimpleNamespace(
        added=["a.py"],
        modified=["b.py"],
        deleted=["c.py"],
        removed_symbols=["old_fn"],
        new_public_symbols=["new_fn"],
    )

    retirement = [{"adr": "ADR-001", "verified": True}]

    mentions_obj = MagicMock()
    mentions_obj.as_dict.return_value = {
        "answer": {"mentions": ["ADR-002"]},
        "limits": {"max": 5},
    }

    law_facts_instance = MagicMock()
    law_facts_instance.decisions_mentioning.return_value = mentions_obj

    git_instance = MagicMock()
    git_instance.adr_refs_in_history.return_value = ["ADR-009"]

    look_alikes_value = [{"candidate": "z.py"}]
    find_look_alikes_mock = AsyncMock(return_value=look_alikes_value)

    cognitive_service = MagicMock()

    with (
        patch(
            "will.autonomy.step_zero.read_patch", return_value=facts
        ) as mock_read_patch,
        patch(
            "will.autonomy.step_zero.verify_retires", return_value=retirement
        ) as mock_verify_retires,
        patch(
            "will.autonomy.step_zero.LawFacts", return_value=law_facts_instance
        ) as mock_law_facts,
        patch(
            "will.autonomy.step_zero.GitService", return_value=git_instance
        ) as mock_git_service,
        patch("will.autonomy.step_zero.find_look_alikes", find_look_alikes_mock),
    ):
        result = asyncio.run(
            build_step_zero_report(
                patch=patch_arg,
                retires=retires,
                repo_root=repo_root,
                cognitive_service=cognitive_service,
            )
        )

    mock_read_patch.assert_called_once_with(patch_arg)
    mock_verify_retires.assert_called_once_with(retires, facts)
    mock_law_facts.assert_called_once_with(repo_root)
    mock_git_service.assert_called_once_with(repo_root)
    law_facts_instance.decisions_mentioning.assert_called_once_with(
        ["a.py", "b.py", "c.py"]
    )
    assert git_instance.adr_refs_in_history.call_count == 2
    find_look_alikes_mock.assert_awaited_once_with(patch_arg, facts, cognitive_service)

    assert result["patch"] == {
        "added": ["a.py"],
        "modified": ["b.py"],
        "deleted": ["c.py"],
        "removed_symbols": ["old_fn"],
        "new_public_symbols": ["new_fn"],
    }
    assert result["retires"] == retirement
    assert result["retires_all_verified"] is True
    assert result["decisions"] == {
        "mentions": ["ADR-002"],
        "history": {"b.py": ["ADR-009"], "c.py": ["ADR-009"]},
        "limits": {"max": 5},
    }
    assert result["look_alikes"] == look_alikes_value
