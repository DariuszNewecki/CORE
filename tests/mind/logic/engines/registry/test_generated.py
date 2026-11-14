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

    # patch.object restores the class state afterwards; plain assignment
    # leaked a MagicMock _discover_engines into every later registry test.
    with (
        patch.object(EngineRegistry, "_discover_engines", MagicMock()) as discover,
        patch.object(EngineRegistry, "_engine_classes", {"fake": FakeEngine}),
    ):
        result = EngineRegistry.engine_source_files()

    assert result == frozenset({"src/mind/logic/engines/fake_engine.py"})
    discover.assert_called_once_with()


# ID: 2f0299fb-ab1a-41fe-a4b1-98d8ecb854ec
def test_EngineRegistry_initialize():
    from mind.logic.engines.registry import EngineRegistry

    path_resolver = MagicMock(name="path_resolver")
    llm_client = MagicMock(name="llm_client")
    embedding_client = MagicMock(name="embedding_client")

    # initialize() rebinds and clears class-level state; patch every touched
    # attribute so the real registry is restored for later tests.
    with (
        patch.object(EngineRegistry, "_discover_engines") as mock_discover,
        patch.object(
            EngineRegistry, "_load_passive_aliases_from_taxonomy"
        ) as mock_aliases,
        patch.object(EngineRegistry, "_path_resolver", None),
        patch.object(EngineRegistry, "_llm_client", None),
        patch.object(EngineRegistry, "_embedding_client", None),
        patch.object(EngineRegistry, "_instances", {}),
        patch.object(EngineRegistry, "_engine_classes", {}),
        patch.object(EngineRegistry, "_discovered", True),
    ):
        EngineRegistry.initialize(
            path_resolver=path_resolver,
            llm_client=llm_client,
            embedding_client=embedding_client,
        )

        assert EngineRegistry._path_resolver is path_resolver
        assert EngineRegistry._llm_client is llm_client
        assert EngineRegistry._embedding_client is embedding_client
        assert EngineRegistry._discovered is False
        mock_discover.assert_called_once()
        mock_aliases.assert_called_once()


# ID: 5fdffcc8-f629-45c3-ad4e-b33a1a309f30
def test_EngineRegistry():
    from mind.logic.engines.registry import EngineRegistry

    mock_resolver = MagicMock()
    mock_engine_cls = MagicMock()
    mock_engine_instance = MagicMock()
    mock_engine_cls.return_value = mock_engine_instance

    saved_classes = dict(EngineRegistry._engine_classes)
    saved_instances = dict(EngineRegistry._instances)
    saved_resolver = EngineRegistry._path_resolver
    saved_llm = EngineRegistry._llm_client
    saved_emb = EngineRegistry._embedding_client
    saved_discovered = EngineRegistry._discovered
    try:
        EngineRegistry._engine_classes = {"dummy_engine": mock_engine_cls}
        EngineRegistry._instances = {}
        EngineRegistry._path_resolver = mock_resolver
        EngineRegistry._llm_client = None
        EngineRegistry._embedding_client = None
        EngineRegistry._discovered = True

        with patch("mind.logic.engines.registry.inspect.signature") as mock_sig:
            mock_sig.return_value = MagicMock(parameters={})
            result = EngineRegistry.get("dummy_engine")

        assert result is mock_engine_instance
        mock_engine_cls.assert_called_once_with()
        # Second call should return cached instance, not re-instantiate.
        with patch("mind.logic.engines.registry.inspect.signature") as mock_sig:
            mock_sig.return_value = MagicMock(parameters={})
            result2 = EngineRegistry.get("dummy_engine")
        assert result2 is mock_engine_instance
        mock_engine_cls.assert_called_once()
    finally:
        EngineRegistry._engine_classes = saved_classes
        EngineRegistry._instances = saved_instances
        EngineRegistry._path_resolver = saved_resolver
        EngineRegistry._llm_client = saved_llm
        EngineRegistry._embedding_client = saved_emb
        EngineRegistry._discovered = saved_discovered


# ID: ef1d5572-6ec7-43d6-b2bc-be7c20711fc1
def test_EngineRegistry_record_engine():
    engine_id = "test_engine"

    # ID: e210cacb-a16c-492a-be9d-d22124e010df
    class FakeRecordEngine:
        supports_records = True

        def __init__(self):
            self.initialized = True

    with (
        patch.object(EngineRegistry, "_discover_engines", MagicMock()) as mock_discover,
        patch.object(
            EngineRegistry,
            "_engine_classes",
            {engine_id: FakeRecordEngine},
            create=True,
        ),
    ):
        result = EngineRegistry.record_engine(engine_id)

    mock_discover.assert_called_once()
    assert isinstance(result, FakeRecordEngine)
    assert result.initialized is True


# ID: 03abc70e-4f84-470f-b939-13b00a49750f
def test_EngineRegistry_record_catalogs() -> None:
    engine_a = MagicMock()
    engine_a.record_catalogs = MagicMock(return_value={"cat_a": {"id": "cat_a"}})
    engine_b = MagicMock()
    engine_b.record_catalogs = MagicMock(return_value={"cat_b": {"id": "cat_b"}})

    with (
        patch.object(
            EngineRegistry,
            "_discover_engines",
            MagicMock(return_value=None),
        ) as mock_discover,
        patch.object(
            EngineRegistry,
            "_engine_classes",
            {"engine_a": engine_a, "engine_b": engine_b},
            create=True,
        ),
    ):
        result = EngineRegistry.record_catalogs()

    mock_discover.assert_called_once_with()
    assert result == {"cat_a": {"id": "cat_a"}, "cat_b": {"id": "cat_b"}}


# ID: ab1b97a9-cd0f-4d3d-89e4-97c83a57e87c
def test_EngineRegistry_known_engine_ids():
    from mind.logic.engines.registry import PASSIVE_ALIASES, EngineRegistry

    original_engine_classes = getattr(EngineRegistry, "_engine_classes", None)
    had_engine_classes = "_engine_classes" in EngineRegistry.__dict__

    # Arrange: pretend discovery already found two engines.
    EngineRegistry._engine_classes = {
        "alpha_engine": MagicMock(),
        "beta_engine": MagicMock(),
    }

    with patch.object(EngineRegistry, "_discover_engines") as mock_discover:
        try:
            # Act
            result = EngineRegistry.known_engine_ids()

            # Assert
            mock_discover.assert_called_once_with()
            assert isinstance(result, frozenset)
            assert result == frozenset({"alpha_engine", "beta_engine"}) | frozenset(
                PASSIVE_ALIASES
            )
            assert "alpha_engine" in result
            assert "beta_engine" in result
            for alias in PASSIVE_ALIASES:
                assert alias in result
        finally:
            if had_engine_classes:
                EngineRegistry._engine_classes = original_engine_classes
            elif "_engine_classes" in EngineRegistry.__dict__:
                del EngineRegistry._engine_classes


import pytest

from mind.logic.engines.registry import DuplicateEngineIdError


# ID: 9c2fd249-32f2-4fb8-9832-41a26e5da3b9
def test_DuplicateEngineIdError():
    message = "engine_id 'foo' declared by both A and B"
    error = DuplicateEngineIdError(message)

    assert isinstance(error, RuntimeError)
    assert str(error) == message
    with pytest.raises(RuntimeError):
        raise error
