from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.v1.project_routes import generate_docs


@pytest.mark.asyncio
# ID: 35b534ce-7e13-45f9-83f0-8d57bd581dac
async def test_generate_docs():
    """Test happy path of generate_docs."""
    # Create mock request with app.state.core_context
    mock_request = MagicMock()
    mock_request.app.state.core_context = MagicMock()
    mock_request.app.state.core_context.git_service.repo_path = "/fake/repo"

    # Create mock session
    mock_session = AsyncMock()

    # Mock the _gen_docs function at its defining module and logger
    with patch(
        "body.introspection.generate_capability_docs.main", new=AsyncMock()
    ) as mock_gen_docs:
        with patch("api.v1.project_routes.logger") as mock_logger:
            # Call the function with a minimal DocsRequest using keyword args
            result = await generate_docs(
                body=MagicMock(output="custom_path.md"),
                request=mock_request,
                session=mock_session,
            )

            # Assert _gen_docs was called with the right args
            mock_gen_docs.assert_awaited_once_with(
                session=mock_session, repo_root="/fake/repo"
            )

            # Assert result structure
            assert result == {
                "output": "docs/10_CAPABILITY_REFERENCE.md",
                "generated": True,
            }

            # Assert logger.error was NOT called (happy path)
            mock_logger.error.assert_not_called()
