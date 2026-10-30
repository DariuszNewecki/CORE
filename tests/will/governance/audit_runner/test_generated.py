from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from will.governance.audit_runner import run_sync_audit


@pytest.mark.asyncio
# ID: 94d79c37-b2aa-4edf-838d-e8f20f534a66
async def test_run_sync_audit(tmp_path):
    # --- auditor_context guard: must not be None ---
    auditor_context = MagicMock()
    auditor_context.db_session = None
    auditor_context.force_llm = False
    auditor_context.intent_repo.root = tmp_path

    # --- context ---
    context = MagicMock()
    context.auditor_context = auditor_context
    context.git_service.get_current_commit.return_value = "a" * 40
    context.git_service.repo_path = tmp_path

    # --- session execute / commit ---
    session = AsyncMock()
    insert_result = MagicMock()
    insert_result.scalar_one.return_value = 42
    session.execute.return_value = insert_result

    # --- path resolver / file service ---
    reports_dir = tmp_path / "reports"
    path_resolver = MagicMock()
    path_resolver.reports_dir = reports_dir
    file_service = MagicMock()

    # --- full-audit (non-filtered) branch ---
    full_results = {
        "findings": [{"id": "F1", "message": "ok"}],
        "executed_rule_ids": ["R2", "R1"],
        "passed": True,
        "stats": {"total": 1},
        "verdict": MagicMock(value="PASS"),
    }
    auditor = MagicMock()
    auditor.run_full_audit_async = AsyncMock(return_value=full_results)

    def _downgrade_side_effect(findings, symbol_index):
        return [dict(f) for f in findings], []

    with (
        patch(
            "will.governance.audit_runner.ConstitutionalAuditor",
            return_value=auditor,
        ),
        patch(
            "will.governance.audit_runner.PathResolver",
        ) as pr_cls,
        patch(
            "will.governance.audit_runner.FileService",
            return_value=file_service,
        ),
        patch(
            "will.governance.audit_runner.apply_entry_point_downgrade",
            side_effect=_downgrade_side_effect,
        ),
        patch(
            "will.governance.audit_runner._blocking_count_from_dicts",
            return_value=0,
        ),
        patch(
            "will.governance.audit_runner._sanitize_payload",
            side_effect=lambda x: x,
        ),
        patch(
            "will.governance.audit_runner.build_auto_ignored_markdown",
            return_value="# auto ignored\n",
        ),
        patch(
            "will.governance.audit_runner._record_run_observation",
            AsyncMock(),
        ),
        patch(
            "will.governance.audit_runner.text",
            MagicMock(),
        ),
    ):
        pr_cls.from_repo.return_value = path_resolver

        result = await run_sync_audit(context, session, force_llm=False, source="api")

    # --- assertions ---
    assert result["passed"] is True
    assert result["findings"] == [{"id": "F1", "message": "ok"}]
    assert result["executed_rule_ids"] == ["R1", "R2"]
    assert result["auto_ignored"] == []
    assert result["run_id"] == "42"

    auditor.run_full_audit_async.assert_awaited_once()
    session.execute.assert_awaited_once()
    session.commit.assert_awaited_once()

    assert context.auditor_context.db_session is None
