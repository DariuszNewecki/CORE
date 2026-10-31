from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from will.workers.test_remediator.worker import TestRemediatorWorker


@pytest.mark.asyncio
# ID: c67a16c3-3e99-41e0-8bc5-e0c8690b2c3b
async def test_TestRemediatorWorker_run():
    worker = TestRemediatorWorker(declaration_name="test_remediator", core_context=None)
    worker.post_heartbeat = AsyncMock()
    worker.post_report = AsyncMock()
    worker.post_observation = AsyncMock()

    mock_config = MagicMock()
    mock_config.blackboard.remediation_cap_n = 3

    mock_evaluator = MagicMock()
    mock_evaluator.execute = AsyncMock(
        return_value=MagicMock(
            ok=True,
            data={
                "gaps": [
                    {
                        "name": "foo",
                        "kind": "function",
                        "signature": "def foo():",
                    }
                ],
                "test_file": "tests/test_mod.py",
                "covered_count": 1,
            },
        )
    )

    with (
        patch(
            "shared.infrastructure.intent.operational_config.load_operational_config",
            return_value=mock_config,
        ),
        patch(
            "body.evaluators.test_gap_evaluator.TestGapEvaluator",
            return_value=mock_evaluator,
        ),
        patch(
            "will.workers.test_remediator.worker._load_open_findings",
            new=AsyncMock(
                return_value=[
                    {
                        "id": "entry-1",
                        "subject": "x::test.runner.missing::mod",
                        "payload": {"source_file": "src/mod.py"},
                    }
                ]
            ),
        ),
        patch(
            "will.workers.test_remediator.worker._get_active_symbol_proposals",
            new=AsyncMock(return_value=set()),
        ),
        patch(
            "will.workers.test_remediator.worker._pending_source",
            return_value=None,
        ),
        patch(
            "will.workers.test_remediator.worker._query_source_file_attempt_count",
            new=AsyncMock(return_value=0),
        ),
        patch(
            "will.workers.test_remediator.worker._query_symbol_failure_lineage",
            new=AsyncMock(return_value=(0, None)),
        ),
        patch(
            "will.workers.test_remediator.worker._create_symbol_proposal",
            new=AsyncMock(return_value="proposal-1"),
        ),
        patch(
            "will.workers.test_remediator.worker._release_entries",
            new=AsyncMock(return_value=1),
        ),
        patch(
            "shared.infrastructure.intent.law_roots.configured_repo_root",
            return_value="/tmp/repo",
        ),
    ):
        await worker.run()

    worker.post_heartbeat.assert_awaited_once()
    mock_evaluator.execute.assert_awaited_once_with(source_file="src/mod.py")
    worker.post_report.assert_awaited_once()
    report_kwargs = worker.post_report.call_args.kwargs
    assert report_kwargs["subject"] == "test_remediator.completed"
    assert report_kwargs["payload"]["proposals_created"] == 1
