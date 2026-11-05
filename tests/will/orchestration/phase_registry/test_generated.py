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
