from __future__ import annotations

from unittest.mock import MagicMock, patch

from mind.logic.engines.registry import EngineRegistry


# ID: 09d12adf-67c1-4350-b23f-41eb6a59b493
def test_engine_registry_get() -> None:
    instance = MagicMock()
    engine_cls = MagicMock(return_value=instance)

    with (
        patch.object(EngineRegistry, "_path_resolver", MagicMock()),
        patch.object(EngineRegistry, "_instances", {}),
        patch.object(EngineRegistry, "_engine_classes", {"my_engine": engine_cls}),
        patch.object(EngineRegistry, "_llm_client", None),
        patch.object(EngineRegistry, "_embedding_client", None),
    ):
        result = EngineRegistry.get("my_engine")

    assert result is instance
    engine_cls.assert_called_once_with()
