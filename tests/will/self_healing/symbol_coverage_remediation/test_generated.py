from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from will.self_healing.symbol_coverage_remediation import remediate_batch_by_symbol


# ID: 26381fd3-e2e6-4449-b8c2-e4cda8319d80
def test_remediate_batch_by_symbol():
    repo_root = Path("/repo")
    context = MagicMock()
    context.git_service.repo_path = repo_root

    candidates = [(repo_root / "a.py", 0.1), (repo_root / "b.py", 0.2)]

    per_file_results = [
        {"status": "completed", "tests_written": 1},
        {"status": "completed", "tests_written": 2},
    ]

    mock_select = AsyncMock(return_value=candidates)
    mock_remediate = AsyncMock(side_effect=per_file_results)
    mock_summary = MagicMock(return_value={"success": 2, "failed": 0, "skipped": 0})

    with (
        patch(
            "will.self_healing.symbol_coverage_remediation.select_batch_candidates",
            mock_select,
        ),
        patch(
            "will.self_healing.symbol_coverage_remediation.remediate_file_by_symbol",
            mock_remediate,
        ),
        patch(
            "will.self_healing.symbol_coverage_remediation._summarize_batch",
            mock_summary,
        ),
    ):
        result = asyncio.run(remediate_batch_by_symbol(context, write=True, count=5))

    mock_select.assert_awaited_once_with(repo_root, 5, max_complexity="MODERATE")
    assert mock_remediate.await_count == 2
    mock_remediate.assert_any_await(context, "a.py", write=True)
    mock_remediate.assert_any_await(context, "b.py", write=True)

    assert result["status"] == "completed"
    assert result["processed"] == 2
    assert result["summary"] == {"success": 2, "failed": 0, "skipped": 0}
    assert result["results"][0] == {
        "file": "a.py",
        "original_coverage": 0.1,
        "status": "completed",
        "tests_written": 1,
    }
    assert result["results"][1] == {
        "file": "b.py",
        "original_coverage": 0.2,
        "status": "completed",
        "tests_written": 2,
    }
    mock_summary.assert_called_once_with(result["results"])
