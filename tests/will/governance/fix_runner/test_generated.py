from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from will.governance.fix_runner import run_and_persist_quality


# ID: 6216af36-3d79-41d1-b022-05a0e507e19f
async def test_run_and_persist_quality():
    context = MagicMock()
    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    run_id = uuid4()

    result_payload = {"ok": True, "summary": "all good"}

    mock_update = AsyncMock()
    mock_lint = AsyncMock(return_value=result_payload)

    with (
        patch("will.governance.fix_runner._update_fix_run_status", mock_update),
        patch("will.governance.fix_runner._run_quality_lint", mock_lint),
    ):
        await run_and_persist_quality(
            context,
            session,
            run_id=run_id,
            check="lint",
            params={"fix": True},
        )

    mock_lint.assert_awaited_once_with(context, fix=True)

    assert mock_update.await_count == 2
    first_call = mock_update.await_args_list[0]
    assert first_call.args[1] == run_id
    assert first_call.args[2] == "executing"
    assert first_call.kwargs.get("started") is True

    second_call = mock_update.await_args_list[1]
    assert second_call.args[1] == run_id
    assert second_call.args[2] == "completed"
    assert second_call.kwargs.get("finished") is True
    assert second_call.kwargs.get("error") is None
    assert second_call.kwargs.get("result") == result_payload


import pytest

from will.governance.fix_runner import run_quality_policy_coverage


@pytest.mark.asyncio
# ID: 61c719b1-beea-4b4a-a31e-f9a19a209e7a
async def test_run_quality_policy_coverage():
    fake_report = MagicMock()
    fake_report.report_id = "rpt-123"
    fake_report.generated_at_utc = "2024-01-01T00:00:00Z"
    fake_report.repo_root = "/repo"
    fake_report.summary = {"total": 3, "covered": 3}
    fake_report.records = [{"policy": "p1", "covered": True}]
    fake_report.exit_code = 0

    context = MagicMock()
    context.git_service.repo_path = "/repo"

    mock_service_cls = MagicMock()
    mock_service_instance = MagicMock()
    mock_service_instance.run.return_value = fake_report
    mock_service_cls.return_value = mock_service_instance

    mock_path_resolver_cls = MagicMock()
    mock_path_resolver_cls.from_repo.return_value = MagicMock()

    with (
        patch(
            "mind.governance.policy_coverage_service.PolicyCoverageService",
            mock_service_cls,
        ),
        patch("shared.path_resolver.PathResolver", mock_path_resolver_cls),
        patch(
            "will.governance.fix_runner.intent_root_for", return_value="/repo/intents"
        ),
    ):
        result = await run_quality_policy_coverage(context)

    assert result == {
        "report_id": "rpt-123",
        "generated_at_utc": "2024-01-01T00:00:00Z",
        "repo_root": "/repo",
        "summary": {"total": 3, "covered": 3},
        "records": [{"policy": "p1", "covered": True}],
        "exit_code": 0,
    }
    mock_path_resolver_cls.from_repo.assert_called_once_with(
        repo_root="/repo", intent_root="/repo/intents"
    )
    mock_service_instance.run.assert_called_once_with()


import pytest

from will.governance.fix_runner import run_quality_imports


@pytest.mark.asyncio
# ID: 3a7cda98-a31a-4eec-8036-c8b193564921
async def test_run_quality_imports() -> None:
    context = MagicMock()

    fake_result = MagicMock()
    fake_result.ok = True
    fake_result.data = {"violations": [{"message": "unused import"}]}

    fake_executor = MagicMock()
    fake_executor.execute = AsyncMock(return_value=fake_result)

    with patch(
        "will.governance.fix_runner.ActionExecutor", return_value=fake_executor
    ) as mock_executor_cls:
        result = await run_quality_imports(context)

    mock_executor_cls.assert_called_once_with(context)
    fake_executor.execute.assert_awaited_once_with("check.imports")
    assert result == {
        "status": "ok",
        "violations": [{"message": "unused import"}],
    }


# ID: a9be0595-1bdf-4286-89c5-9adb3a3ec984
def test_bootstrap_ir():
    from will.governance.fix_runner import bootstrap_ir

    context = MagicMock()
    context.file_handler.repo_path = "/repo"

    # PathResolver(root).mind_dir is used to build the rel path; patch it so we
    # don't depend on its internal layout.
    with __import__("unittest").mock.patch(
        "will.governance.fix_runner.PathResolver"
    ) as MockResolver:
        MockResolver.return_value.mind_dir = MagicMock()
        MockResolver.return_value.mind_dir.__truediv__ = lambda self, other: other

        from pathlib import Path

        MockResolver.return_value.mind_dir = Path("/repo/var/mind")

        result = bootstrap_ir(context, "triage")

    assert isinstance(result, str)
    assert result.endswith("var/mind/ir/triage_log.yaml")
    context.file_handler.write_runtime_text.assert_called_once()
    called_rel, called_content = context.file_handler.write_runtime_text.call_args[0]
    assert called_rel == result
    assert "incident_triage_log" in called_content


import pytest


@pytest.mark.asyncio
# ID: f3994a74-3559-4a87-87dc-20773774b35c
async def test_run_and_persist_modularity() -> None:
    from will.governance.fix_runner import run_and_persist_modularity

    run_id = uuid4()
    context = MagicMock()
    session = AsyncMock()

    results = [
        {"file": "a.py", "original_score": 3.1, "success": True, "message": "ok"},
        {"file": "b.py", "original_score": 2.4, "success": True, "message": "ok"},
    ]

    mock_service = MagicMock()
    mock_service.remediate_batch = AsyncMock(return_value=results)

    with (
        patch(
            "will.self_healing.modularity_remediation_service.ModularityRemediationService",
            return_value=mock_service,
        ) as mock_cls,
        patch(
            "will.governance.fix_runner._update_fix_run_status",
            new=AsyncMock(),
        ) as mock_update,
    ):
        await run_and_persist_modularity(
            context,
            session,
            run_id=run_id,
            write=True,
            params={"min_score": 2.0},
        )

    mock_cls.assert_called_once_with(context)
    mock_service.remediate_batch.assert_awaited_once_with(write=True, min_score=2.0)

    statuses = [c.args[2] for c in mock_update.await_args_list]
    assert statuses == ["executing", "completed"]

    final_call = mock_update.await_args_list[-1]
    assert final_call.kwargs["finished"] is True
    payload = final_call.kwargs["result"]
    assert payload["kind"] == "modularity"
    assert payload["ok"] is True
    assert payload["count"] == 2
    assert payload["successes"] == 2
    assert payload["failures"] == 0
    assert payload["files"] == results


# ID: 55acf141-52ed-49d1-815b-5fe5f7578214
def test_list_action_definitions():
    from will.governance.fix_runner import list_action_definitions

    mock_category = MagicMock()
    mock_category.value = "fix"

    mock_def = MagicMock()
    mock_def.action_id = "fix.something"
    mock_def.description = "Does something"
    mock_def.category = mock_category
    mock_def.policies = ("policy_a",)
    mock_def.impact_level = "low"
    mock_def.requires_db = True
    mock_def.requires_vectors = False
    mock_def.remediates = ("issue.x",)

    mock_registry = MagicMock()
    mock_registry.list_all.return_value = [mock_def]

    with (
        patch("body.atomic.action_registry", mock_registry, create=True),
        patch("will.governance.fix_runner.action_registry", mock_registry),
    ):
        result = list_action_definitions(category="fix")

    assert result == [
        {
            "action_id": "fix.something",
            "description": "Does something",
            "category": "fix",
            "policies": ["policy_a"],
            "impact_level": "low",
            "requires_db": True,
            "requires_vectors": False,
            "remediates": ["issue.x"],
        }
    ]


from will.governance.fix_runner import run_and_persist_flow


# ID: 9817f999-5e91-4177-862f-158b4e631317
async def test_run_and_persist_flow() -> None:
    context = MagicMock()
    session = MagicMock()
    run_id = uuid4()
    flow_id = "test_flow"

    step = MagicMock()
    step.ref_id = "step-1"
    step.kind = "check"
    step.ok = True
    step.required = True
    step.duration_sec = 0.5
    step.data = {}

    flow_result = MagicMock()
    flow_result.ok = True
    flow_result.flow_id = flow_id
    flow_result.duration_sec = 1.23
    flow_result.steps = [step]

    mock_executor = MagicMock()
    mock_executor.execute = AsyncMock(return_value=flow_result)

    mock_delegate = MagicMock()
    mock_update = AsyncMock()

    with (
        patch(
            "will.governance.fix_runner._build_cognitive_delegate",
            return_value=mock_delegate,
        ),
        patch(
            "will.governance.fix_runner.FlowExecutor",
            return_value=mock_executor,
        ),
        patch(
            "will.governance.fix_runner._update_fix_run_status",
            mock_update,
        ),
    ):
        await run_and_persist_flow(
            context,
            session,
            run_id=run_id,
            flow_id=flow_id,
            write=False,
            params=None,
        )

    mock_executor.execute.assert_awaited_once_with(flow_id, write=False)
    assert mock_update.await_count == 2
    first_call = mock_update.await_args_list[0]
    assert first_call.args[2] == "executing"
    assert first_call.kwargs.get("started") is True
    final_call = mock_update.await_args_list[1]
    assert final_call.args[2] == "completed"
    assert final_call.kwargs.get("finished") is True


import pytest

from will.governance.fix_runner import run_and_persist_fix


@pytest.mark.asyncio
# ID: 27eece5d-69a0-4e00-b061-323dee715fd7
async def test_run_and_persist_fix():
    context = MagicMock()
    session = MagicMock()
    run_id = uuid4()

    action_result = MagicMock()
    action_result.ok = True
    action_result.data = {"files_changed": 2}
    action_result.duration_sec = 1.5

    mock_executor = MagicMock()
    mock_executor.execute = AsyncMock(return_value=action_result)

    mock_update_status = AsyncMock()

    with (
        patch(
            "will.governance.fix_runner.ActionExecutor",
            return_value=mock_executor,
        ),
        patch(
            "will.governance.fix_runner._update_fix_run_status",
            mock_update_status,
        ),
    ):
        await run_and_persist_fix(
            context,
            session,
            run_id=run_id,
            fix_id="fix.docstrings",
            target_files=["a.py"],
            write=True,
            params={"limit": 5},
        )

    mock_executor.execute.assert_awaited_once_with(
        "fix.docstrings", write=True, target_files=["a.py"], limit=5
    )

    assert mock_update_status.await_count == 2

    first_call = mock_update_status.await_args_list[0]
    assert first_call.args == (session, run_id, "executing")
    assert first_call.kwargs == {"started": True}

    final_call = mock_update_status.await_args_list[1]
    assert final_call.args == (session, run_id, "completed")
    assert final_call.kwargs["finished"] is True
    assert final_call.kwargs["error"] is None
    payload = final_call.kwargs["result"]
    assert payload["kind"] == "atomic"
    assert payload["ok"] is True


# ID: e2d34099-fdf5-41ce-8cd5-2d82bc176390
def test_list_registered_flow_ids():
    from will.governance.fix_runner import list_registered_flow_ids

    definition_a = MagicMock()
    definition_a.flow_id = "flow-alpha"
    definition_b = MagicMock()
    definition_b.flow_id = "flow-beta"

    mock_registry = MagicMock()
    mock_registry.list_all.return_value = [definition_a, definition_b]

    with patch(
        "will.governance.fix_runner.flow_registry",
        mock_registry,
    ):
        result = list_registered_flow_ids()

    assert result == {"flow-alpha", "flow-beta"}
    mock_registry.list_all.assert_called_once_with()


# ID: c3857d5a-e2a9-4e25-8b7d-ca98301b57bc
def test_action_runs_candidate_code():
    from will.governance.fix_runner import action_runs_candidate_code

    definition = MagicMock()
    definition.runs_candidate_code = True

    with patch(
        "body.atomic.action_registry.get",
        return_value=definition,
    ) as mock_get:
        result = action_runs_candidate_code("some.action")

    assert result is True
    mock_get.assert_called_once_with("some.action")




# ID: 108ee86d-069e-4ad1-b9d1-83640fc8db5d
def test_action_mutates_files() -> None:
    from will.governance.fix_runner import action_mutates_files

    mock_definition = MagicMock()
    mock_definition.executor = "some_executor"

    mock_metadata = MagicMock()

    with (
        patch("shared.action_types.ActionImpact") as mock_impact,
        patch("shared.atomic_action.get_action_metadata", return_value=mock_metadata),
        patch(
            "will.governance.fix_runner.action_registry.get",
            return_value=mock_definition,
        ),
    ):
        mock_impact.WRITE_CODE = "write_code"
        mock_impact.WRITE_METADATA = "write_metadata"
        mock_metadata.impact = "write_code"

        assert action_mutates_files("some_action") is True
