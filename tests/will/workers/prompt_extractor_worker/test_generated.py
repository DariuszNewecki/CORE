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
