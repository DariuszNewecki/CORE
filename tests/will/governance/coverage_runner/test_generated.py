from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from will.governance.coverage_runner import run_tests_interactive


# ID: d55ed5e9-4c0d-41af-a27a-d9e001f5ecc8
async def test_run_tests_interactive() -> None:
    fixed_repo_root = "/repo/root"

    mock_git_service = MagicMock()
    mock_git_service.repo_path = fixed_repo_root

    context = MagicMock()
    context.git_service = mock_git_service
    context.cognitive_service = MagicMock()

    mock_file_path = MagicMock()
    mock_file_path.exists.return_value = True
    mock_file_path.is_file.return_value = True

    expected_result = {"ok": True, "tests_generated": 1}

    with (
        patch(
            "will.governance.coverage_runner.remediate_file_by_symbol",
            new=AsyncMock(return_value=expected_result),
        ) as mock_remediate_file,
        patch(
            "will.governance.coverage_runner.resolve_contained_source_path",
            return_value=mock_file_path,
        ),
    ):
        result = await run_tests_interactive(context, target_file="src/example.py")

    assert result == expected_result
    mock_remediate_file.assert_awaited_once_with(context, "src/example.py", write=True)
