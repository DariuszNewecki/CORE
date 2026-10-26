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


# ID: 7b26087c-6240-40c5-a0ac-9f876bbcc006
async def test_IntentInspector_run(tmp_path):
    """Structural findings already open are skipped; a missing .intent/ stops the run."""
    worker = IntentInspector(MagicMock())
    worker.post_heartbeat = AsyncMock()
    worker.post_report = AsyncMock()
    worker.post_artifact_finding = AsyncMock()
    worker._resolve_intent_root = MagicMock(return_value=tmp_path)
    good_meta = {
        "id": "x",
        "title": "X",
        "version": "1",
        "authority": "policy",
        "status": "active",
    }
    worker._load_all_documents = MagicMock(
        return_value=[
            {"path": "a.yaml", "data": {"kind": "k"}, "raw": "", "skip_llm": True},
            {"path": "b.yaml", "data": {"kind": "k"}, "raw": "", "skip_llm": True},
            {
                "path": "ok.yaml",
                "data": {"$schema": "s", "kind": "k", "metadata": good_meta},
                "raw": "",
                "skip_llm": True,
            },
        ]
    )
    worker._load_valid_worker_statuses = MagicMock(return_value={"active"})
    worker._fetch_existing_subjects = AsyncMock(
        return_value={"intent_yaml::intent.inspection.structural::a.yaml"}
    )
    worker._pass_coherence = AsyncMock(return_value=2)
    worker._pass_alignment = AsyncMock(return_value=1)

    await worker.run()

    worker._fetch_existing_subjects.assert_awaited_once_with(
        "intent.inspection.structural"
    )
    worker.post_artifact_finding.assert_awaited_once_with(
        artifact_type="intent_yaml",
        sub_namespace="intent.inspection.structural",
        identity_key_value="b.yaml",
        payload={
            "pass": "structural",
            "path": "b.yaml",
            "issues": ["missing $schema reference"],
            "severity": "warning",
        },
    )
    worker._pass_alignment.assert_awaited_once_with(
        worker._load_all_documents.return_value, tmp_path
    )
    worker.post_report.assert_awaited_once_with(
        subject="intent_inspector.run.complete",
        payload={
            "documents_scanned": 3,
            "structural_findings": 1,
            "coherence_findings": 2,
            "alignment_findings": 1,
            "message": (
                "Inspection complete. 1 structural, 2 coherence, 1 alignment findings."
            ),
        },
    )

    # .intent/ missing: error report, no passes run.
    missing = tmp_path / "absent"
    worker._resolve_intent_root = MagicMock(return_value=missing)
    worker._load_all_documents.reset_mock()
    worker.post_report.reset_mock()

    await worker.run()

    worker._load_all_documents.assert_not_called()
    worker.post_report.assert_awaited_once_with(
        subject="intent_inspector.run.complete",
        payload={"error": f".intent/ not found at {missing}"},
    )
