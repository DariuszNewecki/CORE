from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from will.orchestration.decision_tracer import DecisionTracer


# ID: 6d8dd7cc-30f2-477f-8852-d78c61c81603
async def test_DecisionTracer_save_trace():
    from pathlib import Path

    with (
        patch(
            "will.orchestration.decision_tracer.configured_repo_root",
            return_value=Path("/tmp/repo"),
        ),
        patch("will.orchestration.decision_tracer.PathResolver") as mock_path_resolver,
        patch("will.orchestration.decision_tracer.FileService") as mock_file_service,
    ):
        mock_resolver_instance = MagicMock()
        mock_resolver_instance.reports_dir = Path("/tmp/repo/reports")
        mock_path_resolver.return_value = mock_resolver_instance

        mock_fs_instance = MagicMock()
        mock_fs_instance.ensure_dir = MagicMock()
        mock_file_service.return_value = mock_fs_instance

        tracer = DecisionTracer(
            file_service=mock_fs_instance,
            agent_name="TestAgent",
            goal="TestGoal",
        )

        expected_path = Path("/tmp/trace.json")
        tracer._save_to_file = MagicMock(return_value=expected_path)
        tracer._save_to_database = AsyncMock()

        result = await tracer.save_trace()

        assert result == expected_path
        tracer._save_to_file.assert_called_once()
        tracer._save_to_database.assert_awaited_once_with(expected_path)
