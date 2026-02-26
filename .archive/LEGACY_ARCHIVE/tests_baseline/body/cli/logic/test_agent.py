# tests/body/cli/logic/test_agent.py


import pytest


pytestmark = pytest.mark.legacy

from unittest.mock import AsyncMock, MagicMock, patch


try:
    from body.cli.logic.agent import agent_scaffold

    _AGENT_AVAILABLE = True
except ImportError:  # pragma: no cover
    agent_scaffold = None
    _AGENT_AVAILABLE = False


@pytest.mark.skipif(not _AGENT_AVAILABLE, reason="agent module not available")
def test_agent_scaffold():
    """Test agent_scaffold passes correct kwargs to scaffold_new_application."""
    if not _AGENT_AVAILABLE:
        pytest.skip("agent module not available")

    with patch(
        "body.cli.logic.agent.scaffold_new_application", new_callable=AsyncMock
    ) as mock_scaffold:
        mock_scaffold.return_value = (True, "Application created successfully")

        mock_ctx = MagicMock()
        mock_ctx.obj = MagicMock()  # ← .obj is used

        import asyncio

        asyncio.run(agent_scaffold(mock_ctx, "test_app", "Test goal", True))

        # === CORRECT ASSERTION ===
        mock_scaffold.assert_called_once_with(
            context=mock_ctx.obj,
            project_name="test_app",
            goal="Test goal",
            initialize_git=True,
        )
