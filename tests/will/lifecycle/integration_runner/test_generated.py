from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from will.lifecycle.integration_runner import run_integration


# ID: fb981a44-db34-42cc-afc0-8a5d690132c6
def test_run_integration():
    context = MagicMock()
    commit_message = "test commit"

    mock_integrate = AsyncMock(return_value=None)

    with patch("will.lifecycle.integration_runner.integrate_changes", mock_integrate):
        result = asyncio.run(
            run_integration(context=context, commit_message=commit_message)
        )

    mock_integrate.assert_awaited_once_with(
        context=context, commit_message=commit_message
    )
    assert result == {
        "ok": True,
        "message": "Integration complete.",
        "error": None,
        "exit_code": 0,
    }
