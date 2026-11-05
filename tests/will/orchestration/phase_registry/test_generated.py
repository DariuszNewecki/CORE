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
