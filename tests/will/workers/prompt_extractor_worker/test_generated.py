from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from will.workers.prompt_extractor_worker import PromptExtractorWorker


@pytest.fixture
# ID: 726ba182-b5b0-40f4-8b48-4d352055302c
def mock_core_context():
    """Create a mock CoreContext with cognitive_service and git_service."""
    ctx = MagicMock()
    ctx.cognitive_service = AsyncMock()
    ctx.git_service = MagicMock()
    ctx.registry = AsyncMock()
    return ctx


@pytest.fixture
# ID: c71ef1c5-e66f-40af-9ddb-b40072dd167e
def worker(mock_core_context):
    """Create a PromptExtractorWorker instance with mocked core_context."""
    w = PromptExtractorWorker(core_context=mock_core_context)
    w.post_heartbeat = AsyncMock()
    w.post_report = AsyncMock()
    w.post_artifact_finding = AsyncMock()
    return w


# ID: 7a0862ee-31fb-4545-8c2a-57df5ffac48e
async def test_PromptExtractorWorker(worker, mock_core_context):
    """Happy path: worker processes one finding and posts extraction result."""
    # Arrange: fixture data
    finding = {
        "id": "finding-1",
        "payload": {
            "file_path": "src/main.py",
            "line_number": 42,
        },
    }
    source_code = "line 41\nline 42\nline 43"
    extraction_json = '{"prompt_text": "hello", "suggested_name": "greet", "input_vars": ["name"], "confidence": 0.8}'

    # Mock _claim_open_findings
    mock_blackboard_svc = AsyncMock()
    mock_blackboard_svc.claim_open_findings.return_value = [finding]
    mock_blackboard_svc.update_entry_status = AsyncMock()
    mock_core_context.registry.get_blackboard_service.return_value = mock_blackboard_svc

    # Mock _extract_context
    worker._extract_context = MagicMock(return_value=source_code)

    # Mock PromptModel
    mock_model = AsyncMock()
    mock_model.manifest = MagicMock()
    mock_model.manifest.role = "test-role"
    mock_model.invoke.return_value = extraction_json
    mock_model_instance = MagicMock()
    mock_model_instance.load = MagicMock(return_value=mock_model)
    mock_ai_prompt_module = MagicMock()
    mock_ai_prompt_module.PromptModel = mock_model_instance

    # Mock cognitive_service client
    mock_client = AsyncMock()
    mock_core_context.cognitive_service.aget_client_for_role.return_value = mock_client

    # Mock git_service repo_path
    mock_core_context.git_service.repo_path = Path("/fake/repo")

    # Act
    with patch.dict("sys.modules", {"shared.ai.prompt_model": mock_ai_prompt_module}):
        await worker.run()

    # Assert: post_heartbeat called
    worker.post_heartbeat.assert_awaited_once()

    # Assert: claimed findings
    mock_blackboard_svc.claim_open_findings.assert_awaited_once()

    # Assert: _extract_context called with correct path
    worker._extract_context.assert_called_once_with(Path("/fake/repo/src/main.py"), 42)

    # Assert: PromptModel invoked
    mock_model.invoke.assert_awaited_once_with(
        context={
            "file_path": "src/main.py",
            "line_number": "42",
            "source_code": source_code,
        },
        client=mock_client,
        user_id="prompt_extractor_worker",
    )

    # Assert: post_artifact_finding called
    worker.post_artifact_finding.assert_awaited_once_with(
        artifact_type="python",
        sub_namespace="prompt.extraction",
        identity_key_value="src/main.py::42",
        payload={
            "source_finding_id": "finding-1",
            "source_rule": "ai.prompt.model_required",
            "file_path": "src/main.py",
            "line_number": 42,
            "prompt_text": "hello",
            "suggested_name": "greet",
            "input_vars": ["name"],
            "confidence": 0.8,
            "needs_human": False,
            "status": "open",
        },
    )

    # Assert: finding marked as resolved
    mock_blackboard_svc.update_entry_status.assert_awaited_once_with(
        "finding-1", "resolved"
    )

    # Assert: post_report called with summary
    worker.post_report.assert_awaited_with(
        subject="prompt_extractor_worker.run.complete",
        payload={
            "processed": 1,
            "failed": 0,
            "message": "Run complete. 1 extracted, 0 failed.",
        },
    )


# ID: f23d9875-d454-45c5-ba97-670776b3a450
async def test_PromptExtractorWorker_run(worker, mock_core_context, tmp_path):
    """Mixed batch: unreadable file and LLM failure are abandoned; a
    low-confidence extraction is posted as needs_human with non-ASCII text
    sanitized; a confident one is posted open. Report counts 2 / 2."""
    from will.workers.prompt_extractor_worker import _CFG

    (tmp_path / "src").mkdir()
    for name in ("llm_fails.py", "low.py", "high.py"):
        (tmp_path / "src" / name).write_text(
            "a = 1\nmake_request_async('prompt')\nb = 2\n", encoding="utf-8"
        )
    mock_core_context.git_service.repo_path = tmp_path

    findings = [
        {"id": "f-missing", "payload": {"file_path": "src/gone.py", "line_number": 1}},
        {"id": "f-llm", "payload": {"file_path": "src/llm_fails.py", "line_number": 2}},
        {"id": "f-low", "payload": {"file_path": "src/low.py", "line_number": 2}},
        {"id": "f-high", "payload": {"file_path": "src/high.py", "line_number": 2}},
    ]
    bb_svc = AsyncMock()
    bb_svc.claim_open_findings.return_value = findings
    mock_core_context.registry.get_blackboard_service.return_value = bb_svc

    responses = {
        "src/low.py": '{"prompt_text": "h\\u00e9llo", "suggested_name": "n\\u00e4me",'
        ' "input_vars": ["v\\u00f6"], "confidence": 0.3}',
        "src/high.py": '{"prompt_text": "hello", "suggested_name": "greet",'
        ' "input_vars": ["name"], "confidence": 0.9}',
    }

    async def _invoke(*, context, client, user_id):
        if context["file_path"] == "src/llm_fails.py":
            raise RuntimeError("LLM down")
        assert "make_request_async" in context["source_code"]
        return responses[context["file_path"]]

    model = MagicMock()
    model.manifest.role = "extractor-role"
    model.invoke = AsyncMock(side_effect=_invoke)
    prompt_module = MagicMock()
    prompt_module.PromptModel.load.return_value = model

    with patch.dict("sys.modules", {"shared.ai.prompt_model": prompt_module}):
        await worker.run()

    worker.post_heartbeat.assert_awaited_once()
    bb_svc.claim_open_findings.assert_awaited_once_with(
        "python::ai.prompt.model_required::%", _CFG.claim_limit
    )
    prompt_module.PromptModel.load.assert_called_once_with("prompt_extractor")
    mock_core_context.cognitive_service.aget_client_for_role.assert_awaited_once_with(
        "extractor-role"
    )

    statuses = [c.args for c in bb_svc.update_entry_status.await_args_list]
    assert statuses == [
        ("f-missing", "abandoned"),
        ("f-llm", "abandoned"),
        ("f-low", "resolved"),
        ("f-high", "resolved"),
    ]

    posted = [c.kwargs for c in worker.post_artifact_finding.await_args_list]
    assert [p["identity_key_value"] for p in posted] == [
        "src/low.py::2",
        "src/high.py::2",
    ]
    low, high = posted[0]["payload"], posted[1]["payload"]
    assert low["prompt_text"] == "h?llo"
    assert low["suggested_name"] == "n?me"
    assert low["input_vars"] == ["v?"]
    assert low["needs_human"] is True
    assert low["status"] == "needs_human"
    assert low["source_finding_id"] == "f-low"
    assert high["needs_human"] is False
    assert high["status"] == "open"
    assert high["confidence"] == 0.9

    worker.post_report.assert_awaited_once_with(
        subject="prompt_extractor_worker.run.complete",
        payload={
            "processed": 2,
            "failed": 2,
            "message": "Run complete. 2 extracted, 2 failed.",
        },
    )


# ID: b22792a9-a963-4f3a-8d5a-200d47e563ee
async def test_PromptExtractorWorker_run_no_findings(worker, mock_core_context):
    """With nothing to claim, run() reports zero and never loads the model."""
    bb_svc = AsyncMock()
    bb_svc.claim_open_findings.return_value = []
    mock_core_context.registry.get_blackboard_service.return_value = bb_svc
    prompt_module = MagicMock()

    with patch.dict("sys.modules", {"shared.ai.prompt_model": prompt_module}):
        await worker.run()

    prompt_module.PromptModel.load.assert_not_called()
    worker.post_artifact_finding.assert_not_awaited()
    bb_svc.update_entry_status.assert_not_awaited()
    worker.post_report.assert_awaited_once_with(
        subject="prompt_extractor_worker.run.complete",
        payload={"processed": 0, "message": "No unprocessed findings to extract."},
    )
