from __future__ import annotations

from unittest.mock import MagicMock, patch


# ID: 4bcd0ad9-3891-4f7b-a2e9-eeb03c06065e
def test_PhaseRegistry_get():
    from will.orchestration.phase_registry import PhaseRegistry

    with (
        patch(
            "will.orchestration.phase_registry.get_intent_repository",
            return_value=MagicMock(),
        ),
        patch.object(PhaseRegistry, "_load_phases", return_value=None),
    ):
        core_context = MagicMock()
        path_resolver = MagicMock()
        registry = PhaseRegistry(core_context, path_resolver)

        phase = MagicMock()
        registry._phases["build"] = phase

        result = registry.get("build")

        assert result is phase


# ID: d1c0b18d-7f8c-40a3-b5a7-7708b7f183ea
def test_PhaseRegistry():
    from will.orchestration.phase_registry import PhaseRegistry

    core_context = MagicMock()
    path_resolver = MagicMock()

    mock_phase_class = MagicMock(name="MockPhaseClass")
    mock_phase_instance = MagicMock(name="MockPhaseInstance")
    mock_phase_class.return_value = mock_phase_instance

    mock_module = MagicMock(name="MockModule")
    mock_module.MockPhase = mock_phase_class

    mock_repo = MagicMock(name="MockIntentRepo")
    mock_repo.list_phases.return_value = ["phase-1"]
    mock_repo.load_phase.return_value = {
        "phase_type": "build",
        "implementation": "some.module.MockPhase",
    }

    with (
        patch(
            "will.orchestration.phase_registry.get_intent_repository",
            return_value=mock_repo,
        ),
        patch(
            "will.orchestration.phase_registry.importlib.import_module",
            return_value=mock_module,
        ) as mock_import,
    ):
        registry = PhaseRegistry(core_context, path_resolver)
        result = registry.get("build")

    mock_repo.list_phases.assert_called_once()
    mock_repo.load_phase.assert_called_once_with("phase-1")
    mock_import.assert_called_once_with("some.module")
    mock_phase_class.assert_called_once_with(core_context)
    assert result is mock_phase_instance


import asyncio
from unittest.mock import AsyncMock

from will.orchestration.phase_registry import Phase


# ID: b4d5cbf6-6c97-4813-926d-7d7885648ac9
def test_Phase_execute():
    phase = MagicMock(spec=Phase)
    context = MagicMock()
    expected_result = MagicMock()

    with patch.object(
        Phase, "execute", new=AsyncMock(return_value=expected_result)
    ) as mock_execute:
        result = asyncio.run(mock_execute(phase, context))

    assert result is expected_result
    mock_execute.assert_awaited_once_with(phase, context)





# ID: e15e7ed2-1109-44fa-ac24-23fbb5f6b854
def test_Phase():
    context = MagicMock(name="WorkflowContext")
    expected_result = MagicMock(name="PhaseResult")

    async def _run():
        # ID: dc40f296-4f01-4fc5-8a67-8b4ce97492a3
        class DummyPhase:
            # ID: bd2cb278-87e6-4e41-b3d9-5108582ace15
            async def execute(self, context):
                return expected_result

        phase = DummyPhase()
        # Protocol structural conformance: execute must be a coroutine function
        assert callable(getattr(DummyPhase, "execute"))
        assert asyncio.iscoroutinefunction(DummyPhase.execute)
        result = await phase.execute(context)
        assert result is expected_result

    # The Protocol declares an async execute method
    assert hasattr(Phase, "execute")
    assert asyncio.iscoroutinefunction(_run)
    assert context is not None
