from __future__ import annotations

from unittest.mock import AsyncMock, patch

from api.v1.lint_routes import lint_endpoint


# ID: 80308933-b6e3-4d9d-bb40-722bbb2086a9
async def test_lint_endpoint() -> None:
    expected_result = {
        "ok": True,
        "tools": {
            "black": {"returncode": 0, "stdout": "All good!", "stderr": ""},
            "ruff": {"returncode": 0, "stdout": "All clean!", "stderr": ""},
        },
    }
    with patch("api.v1.lint_routes.run_lint", new_callable=AsyncMock) as mock_run_lint:
        mock_run_lint.return_value = expected_result
        result = await lint_endpoint()
        assert result == expected_result
        mock_run_lint.assert_awaited_once_with()
