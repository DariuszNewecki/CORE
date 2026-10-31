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


from types import SimpleNamespace

import pytest

from will.self_healing.symbol_coverage_remediation import remediate_file_by_symbol


@pytest.mark.asyncio
# ID: fc7b3f7e-8a2d-47ec-9142-e8acc7ecf59c
async def test_remediate_file_by_symbol(tmp_path: Path) -> None:
    source_file = "src/pkg/mod.py"
    source_path = tmp_path / "src" / "pkg" / "mod.py"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("def foo():\n    return 1\n")

    context = MagicMock()
    context.git_service.repo_path = tmp_path
    context.git_service.get_current_commit = MagicMock(return_value="abc123")

    gap_result = SimpleNamespace(
        ok=True,
        data={
            "gaps": [
                {"name": "foo", "kind": "function", "signature": "def foo():"},
            ],
            "test_file": "tests/test_mod.py",
        },
    )
    mock_evaluator = MagicMock()
    mock_evaluator.execute = AsyncMock(return_value=gap_result)

    flow_result = SimpleNamespace(ok=True)

    mock_executor = MagicMock()
    mock_executor.execute = AsyncMock(return_value=flow_result)

    scoped_git = MagicMock()
    scoped_git.cleanup = MagicMock()

    scoped_context = MagicMock()

    mock_sandbox = MagicMock()
    mock_sandbox.build_flow_execution_context = MagicMock(
        return_value=(scoped_context, scoped_git)
    )
    mock_sandbox.checkpoint_paths = MagicMock(return_value=[])
    mock_sandbox.restore_paths = MagicMock()
    mock_sandbox.propagate_changes = MagicMock(return_value={"tests/test_mod.py"})

    with (
        patch(
            "will.self_healing.symbol_coverage_remediation.resolve_contained_source_path",
            return_value=source_path,
        ),
        patch(
            "will.self_healing.symbol_coverage_remediation.TestGapEvaluator",
            return_value=mock_evaluator,
        ),
        patch(
            "will.self_healing.symbol_coverage_remediation.SandboxLifecycle",
            return_value=mock_sandbox,
        ),
        patch(
            "will.self_healing.symbol_coverage_remediation.TestGenCognitiveDelegate",
            return_value=MagicMock(),
        ),
        patch(
            "will.self_healing.symbol_coverage_remediation.FlowExecutor",
            return_value=mock_executor,
        ),
        patch(
            "will.self_healing.symbol_coverage_remediation.declared_production",
            return_value={"tests/test_mod.py"},
        ),
        patch(
            "will.self_healing.symbol_coverage_remediation.test_file_ancestor_init_paths",
            return_value=[],
        ),
    ):
        result = await remediate_file_by_symbol(context, source_file, write=True)

    assert result["status"] == "completed"
    assert result["source_file"] == source_file
    assert result["test_file"] == "tests/test_mod.py"
    assert result["summary"] == {
        "gaps": 1,
        "succeeded": 1,
        "failed": 0,
        "skipped": 0,
    }
    assert "tests/test_mod.py" in result["files_produced"]
    mock_executor.execute.assert_awaited_once()
    scoped_git.cleanup.assert_called_once()
