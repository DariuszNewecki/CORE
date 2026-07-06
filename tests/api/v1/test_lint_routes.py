# tests/api/v1/test_lint_routes.py

"""Unit tests for lint_routes (ADR-054 Phase 1).

POST /lint always returns 200 — lint findings are not HTTP errors. The
`ok` field in the response body carries the pass/fail verdict.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from api.v1.lint_routes import lint_endpoint


async def test_lint_endpoint_returns_ok_true_on_clean_tree():
    """All linters passing → ok=True, 200 (not an error)."""
    result = {
        "ok": True,
        "tools": {
            "black": {"returncode": 0, "stdout": "", "stderr": ""},
            "ruff": {"returncode": 0, "stdout": "", "stderr": ""},
        },
    }
    with patch(
        "api.v1.lint_routes.run_lint",
        new=AsyncMock(return_value=result),
    ) as mock_lint:
        out = await lint_endpoint()

    mock_lint.assert_awaited_once()
    assert out["ok"] is True


async def test_lint_endpoint_returns_ok_false_on_findings():
    """Linting findings → ok=False, still 200.

    A dirty lint result is NOT translated to an HTTP error — the caller
    inspects `ok` to decide whether to block. Per-tool output is preserved
    so the CLI can render the actual findings.
    """
    result = {
        "ok": False,
        "tools": {
            "black": {"returncode": 1, "stdout": "would reformat src/body/foo.py", "stderr": ""},
            "ruff": {"returncode": 0, "stdout": "", "stderr": ""},
        },
    }
    with patch(
        "api.v1.lint_routes.run_lint",
        new=AsyncMock(return_value=result),
    ):
        out = await lint_endpoint()

    assert out["ok"] is False
    assert out["tools"]["black"]["returncode"] == 1
    assert "src/body/foo.py" in out["tools"]["black"]["stdout"]


async def test_lint_endpoint_delegates_to_run_lint_no_args():
    """lint_endpoint calls run_lint() with no arguments."""
    with patch(
        "api.v1.lint_routes.run_lint",
        new=AsyncMock(return_value={"ok": True, "tools": {}}),
    ) as mock_lint:
        await lint_endpoint()

    mock_lint.assert_awaited_once_with()
