from __future__ import annotations


import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from will.test_generation.sandbox import PytestSandboxRunner


@pytest.mark.asyncio
# ID: 6984c5b5-b9c6-4573-8a78-25d3fbe4ad30
async def test_PytestSandboxRunner_run():
    file_handler = MagicMock()
    runner = PytestSandboxRunner(file_handler=file_handler, repo_root="/tmp/repo")

    workspace = MagicMock()
    workspace.get_crate_content.return_value = {"src/foo.py": "print('hi')"}

    fake_result = MagicMock()
    fake_result.status = "ok"
    fake_result.ok = True
    fake_result.passed_ids = ["test_generated.test_thing"]
    fake_result.failed_ids = []
    fake_result.stdout = ""
    fake_result.stderr = ""
    fake_result.reason = ""

    with patch(
        "will.test_generation.sandbox.run_in_sandbox",
        AsyncMock(return_value=fake_result),
    ) as mock_run_in_sandbox:
        result = await runner.run(
            code="def test_thing():\n    assert True\n",
            symbol_name="thing",
            timeout_seconds=30,
            workspace=workspace,
        )

    mock_run_in_sandbox.assert_awaited_once()
    args, kwargs = mock_run_in_sandbox.call_args
    assert args[0] == runner._repo_root
    assert args[1] == ["test_thing_sandbox.py"]
    assert kwargs["timeout_sec"] == 30
    overlay = kwargs["overlay"]
    assert ("src/foo.py", b"print('hi')") in overlay
    assert any(rel == "test_thing_sandbox.py" for rel, _ in overlay)

    assert result.passed is True
    assert result.error == ""
    assert result.total_tests == 1
