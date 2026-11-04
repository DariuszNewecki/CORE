from __future__ import annotations

from unittest.mock import MagicMock, patch

from will.test_generation.phases.parse_phase import ParsePhase


# ID: e61e2003-49d8-47de-a220-0a7e25f14b24
async def test_ParsePhase_execute(tmp_path):
    mock_git_service = MagicMock()
    mock_git_service.repo_path = tmp_path

    mock_context = MagicMock()
    mock_context.git_service = mock_git_service

    phase = ParsePhase(mock_context)

    target_file = tmp_path / "existing_file.py"
    target_file.write_text("content")

    with patch("will.test_generation.phases.parse_phase.logger") as mock_logger:
        result = await phase.execute("existing_file.py")

    assert result is True
    mock_logger.info.assert_called_once()
    mock_logger.error.assert_not_called()


import asyncio


# ID: 76b8b1ee-1a3d-4900-86a4-3fdeca113e16
def test_ParsePhase(tmp_path):
    file_path = "some/file.py"
    abs_file = tmp_path / file_path
    abs_file.parent.mkdir(parents=True, exist_ok=True)
    abs_file.write_text("content")

    context = MagicMock()
    context.git_service.repo_path = tmp_path

    phase = ParsePhase(context)

    result = asyncio.run(phase.execute(file_path))

    assert result is True
