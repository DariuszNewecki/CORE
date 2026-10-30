from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from will.test_generation.phases.load_phase import LoadPhase


# ID: c5308592-d762-45ba-94f4-061b6438fdb9
async def test_LoadPhase_execute():
    context = MagicMock()
    context.registry = MagicMock()
    cognitive = MagicMock(name="cognitive")
    qdrant = MagicMock(name="qdrant")
    session_factory = MagicMock(name="session_factory")
    context.registry.get_cognitive_service = AsyncMock(return_value=cognitive)
    context.registry.get_qdrant_service = AsyncMock(return_value=qdrant)
    context.registry.session = session_factory
    context.git_service = MagicMock()
    context.git_service.repo_path = "/tmp/repo"

    load_phase = LoadPhase(context=context)

    with patch(
        "will.test_generation.phases.load_phase.ContextService", autospec=True
    ) as mock_context_service:
        mock_instance = MagicMock(name="ContextServiceInstance")
        mock_context_service.return_value = mock_instance

        result = await load_phase.execute()

    assert result is mock_instance
    mock_context_service.assert_called_once_with(
        qdrant_client=qdrant,
        cognitive_service=cognitive,
        project_root="/tmp/repo",
        session_factory=session_factory,
    )
    context.registry.get_cognitive_service.assert_awaited_once()
    context.registry.get_qdrant_service.assert_awaited_once()




# ID: 576f907f-f56d-4c4b-b7e0-f244c87b445a
async def test_LoadPhase():
    cognitive_service = MagicMock(name="cognitive_service")
    qdrant_service = MagicMock(name="qdrant_service")
    session_factory = MagicMock(name="session_factory")
    repo_path = "/tmp/repo"

    registry = MagicMock()
    registry.get_cognitive_service = AsyncMock(return_value=cognitive_service)
    registry.get_qdrant_service = AsyncMock(return_value=qdrant_service)
    registry.session = session_factory

    git_service = MagicMock()
    git_service.repo_path = repo_path

    context = MagicMock()
    context.registry = registry
    context.git_service = git_service

    fake_context_service = MagicMock(name="ContextService")

    with patch(
        "will.test_generation.phases.load_phase.ContextService",
        return_value=fake_context_service,
    ) as mock_context_service_cls:
        phase = LoadPhase(context=context)
        result = await phase.execute()

    assert result is fake_context_service
    mock_context_service_cls.assert_called_once_with(
        qdrant_client=qdrant_service,
        cognitive_service=cognitive_service,
        project_root=str(repo_path),
        session_factory=session_factory,
    )
    registry.get_cognitive_service.assert_awaited_once()
    registry.get_qdrant_service.assert_awaited_once()
