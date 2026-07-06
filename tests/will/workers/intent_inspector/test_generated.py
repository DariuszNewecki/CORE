from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from will.workers.intent_inspector import IntentInspector


# ID: a9ec7a44-1e58-4ff6-b52b-fa5157802cf9
async def test_IntentInspector():
    # Arrange
    core_context = MagicMock()
    core_context.git_service.repo_path = "/fake/path"
    core_context.cognitive_service.aget_client_for_role = AsyncMock(
        return_value=MagicMock()
    )
    core_context.registry.get_blackboard_service = AsyncMock(return_value=MagicMock())
    worker = IntentInspector(core_context)

    # Mock post methods
    worker.post_heartbeat = AsyncMock()
    worker.post_report = AsyncMock()
    worker.post_observation = AsyncMock()
    worker.post_artifact_finding = AsyncMock()

    # Mock helper methods that do file I/O
    worker._resolve_intent_root = MagicMock(return_value=MagicMock())
    worker._resolve_intent_root.return_value.exists = MagicMock(return_value=True)
    worker._load_all_documents = MagicMock(
        return_value=[
            {
                "path": "test.yaml",
                "data": {
                    "$schema": "test-schema",
                    "kind": "test",
                    "metadata": {"id": "test-id", "status": "active"},
                },
                "raw": "test: content",
                "skip_llm": False,
            }
        ]
    )
    worker._load_valid_worker_statuses = MagicMock(return_value={"active", "inactive"})
    worker._fetch_existing_subjects = AsyncMock(return_value=set())

    # Mock pass methods
    worker._pass_structural = MagicMock(return_value=[])
    worker._pass_coherence = AsyncMock(return_value=0)
    worker._pass_alignment = AsyncMock(return_value=0)

    # Act
    await worker.run()

    # Assert
    worker.post_heartbeat.assert_awaited_once()
    worker._pass_structural.assert_called_once()
    worker._pass_coherence.assert_awaited_once()
    worker._pass_alignment.assert_awaited_once()
    worker.post_report.assert_awaited_once()
    assert (
        worker.post_report.await_args.kwargs["subject"]
        == "intent_inspector.run.complete"
    )
    assert worker.post_report.await_args.kwargs["payload"]["documents_scanned"] == 1
