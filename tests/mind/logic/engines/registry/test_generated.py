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


# ID: 262eb3c8-7c24-4c03-bc7c-8813de22a178
def test_EngineRegistry_graph_dependent_engine_files() -> None:
    from mind.logic.engines.registry import EngineRegistry

    # ID: 7d00c18d-4696-48e9-b578-0c17be03a4f9
    class GraphEngine:
        requires_knowledge_graph = True

    # ID: 64a3479f-5b09-4628-a3aa-d8cf2bd67214
    class PlainEngine:
        requires_knowledge_graph = False

    GraphEngine.__module__ = "mind.logic.engines.graph_engine"
    PlainEngine.__module__ = "mind.logic.engines.plain_engine"

    with (
        patch.object(
            EngineRegistry,
            "_discover_engines",
            MagicMock(return_value=None),
        ),
        patch.object(
            EngineRegistry,
            "_engine_classes",
            {"graph": GraphEngine, "plain": PlainEngine},
            create=True,
        ),
    ):
        result = EngineRegistry.graph_dependent_engine_files()

    assert result == frozenset({"src/mind/logic/engines/graph_engine.py"})




# ID: 702a9441-74a1-4307-827b-6d76758fe3e7
def test_EngineRegistry_engine_source_files():
    from mind.logic.engines.registry import EngineRegistry

    # ID: db4b12cf-dd3e-4870-b305-8fcc14ec70ce
    class FakeEngine:
        pass

    FakeEngine.__module__ = "mind.logic.engines.fake_engine"

    registry = EngineRegistry
    registry._discover_engines = MagicMock()
    registry._engine_classes = {"fake": FakeEngine}

    result = registry.engine_source_files()

    assert result == frozenset({"src/mind/logic/engines/fake_engine.py"})
    registry._discover_engines.assert_called_once_with()
