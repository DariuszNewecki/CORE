from __future__ import annotations

from unittest.mock import call, patch

from mind.enforcement.audit import lint


# ID: 77a91783-0201-4d55-93c8-96194752eb72
def test_lint():
    with patch("mind.enforcement.audit.run_poetry_command") as mock_run:
        lint()

    assert mock_run.call_args_list == [
        call(
            "🔎 Checking code format with Black...",
            ["black", "--check", "src", "tests"],
        ),
        call(
            "🔎 Checking code quality with Ruff...", ["ruff", "check", "src", "tests"]
        ),
    ]


from unittest.mock import AsyncMock, MagicMock

from mind.enforcement.audit import run_audit_workflow


# ID: cbfc8d61-8b7c-49ea-92f3-8ca21fd8964f
async def test_run_audit_workflow():
    context = MagicMock()
    auditor_context = MagicMock()
    context.auditor_context = auditor_context
    context.qdrant_service = MagicMock()

    expected_result = {"passed": True, "findings": [], "verdict": "PASS", "stats": {}}

    with patch("mind.enforcement.audit.ConstitutionalAuditor") as mock_auditor_cls:
        mock_auditor = MagicMock()
        mock_auditor.run_full_audit_async = AsyncMock(return_value=expected_result)
        mock_auditor_cls.return_value = mock_auditor

        result = await run_audit_workflow(context)

    mock_auditor_cls.assert_called_once_with(auditor_context)
    mock_auditor.run_full_audit_async.assert_awaited_once()
    assert result == expected_result
