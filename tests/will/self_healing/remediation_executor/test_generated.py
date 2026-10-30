from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from will.self_healing.remediation_executor import RemediationExecutor


# ID: b6b76186-549e-40e2-8a1f-ed998ae2404d
async def test_RemediationExecutor_execute() -> None:
    file_handler = MagicMock()
    repo_root = MagicMock()

    executor = RemediationExecutor(file_handler=file_handler, repo_root=repo_root)

    finding = MagicMock()
    finding.check_id = "check-123"
    finding.file_path = "src/example.py"

    matched = MagicMock()
    matched.finding = finding
    matched.pattern.action_handler = "test_handler"

    handler = AsyncMock()
    handler_result = MagicMock()
    handler_result.ok = True
    handler_result.error_message = None
    handler.return_value = handler_result

    executor._get_handler = MagicMock(return_value=handler)

    result = await executor.execute([matched], write=True)

    assert len(result) == 1
    detail = result[0]
    assert detail.finding_id == "check-123"
    assert detail.file_path == "src/example.py"
    assert detail.action_handler == "test_handler"
    assert detail.status == "success"
    assert detail.error_message is None

    executor._get_handler.assert_called_once_with("test_handler")
    handler.assert_awaited_once()
    call_kwargs = handler.await_args.kwargs
    assert call_kwargs["finding"] is finding
    assert call_kwargs["file_handler"] is file_handler
    assert call_kwargs["repo_root"] is repo_root
    assert call_kwargs["write"] is True


from unittest.mock import patch


# ID: 0c4ea628-0af3-45b0-90ee-36473e054c0e
async def test_RemediationExecutor() -> None:
    file_handler = MagicMock()
    repo_root = MagicMock()

    executor = RemediationExecutor(file_handler=file_handler, repo_root=repo_root)

    finding = MagicMock()
    finding.check_id = "check-1"
    finding.file_path = "src/module.py"

    fixed_result = MagicMock()
    fixed_result.ok = True
    fixed_result.error_message = None
    handler = AsyncMock(return_value=fixed_result)

    pattern = MagicMock()
    pattern.action_handler = "sort_imports"

    match = MagicMock()
    match.pattern = pattern
    match.finding = finding

    with patch.object(executor, "_get_handler", return_value=handler):
        result = await executor.execute([match], write=True)

    assert len(result) == 1
    detail = result[0]
    assert detail.finding_id == "check-1"
    assert detail.file_path == "src/module.py"
    assert detail.action_handler == "sort_imports"
    assert detail.status == "success"
    handler.assert_awaited_once_with(
        finding=finding,
        file_handler=file_handler,
        repo_root=repo_root,
        write=True,
    )
