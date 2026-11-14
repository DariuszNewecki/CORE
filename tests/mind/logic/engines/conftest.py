"""Fixtures for the engine tests."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

import mind.logic.engines.registry as registry_module
from mind.logic.engines.registry import EngineRegistry
from shared.path_resolver import PathResolver


_REPO_ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture
def fresh_engine_registry() -> Iterator[type[EngineRegistry]]:
    """The registry freshly initialized on this checkout with no LLM client
    (ADR-176 baseline, #1339). Its class-level state is restored afterwards,
    so tests elsewhere see the registry as they left it."""
    saved = (
        dict(EngineRegistry._instances),
        dict(EngineRegistry._engine_classes),
        EngineRegistry._path_resolver,
        EngineRegistry._llm_client,
        EngineRegistry._embedding_client,
        EngineRegistry._discovered,
        set(registry_module.PASSIVE_ALIASES),
    )
    EngineRegistry.initialize(PathResolver.from_repo(_REPO_ROOT))
    try:
        yield EngineRegistry
    finally:
        EngineRegistry._instances.clear()
        EngineRegistry._instances.update(saved[0])
        EngineRegistry._engine_classes.clear()
        EngineRegistry._engine_classes.update(saved[1])
        EngineRegistry._path_resolver = saved[2]
        EngineRegistry._llm_client = saved[3]
        EngineRegistry._embedding_client = saved[4]
        EngineRegistry._discovered = saved[5]
        registry_module.PASSIVE_ALIASES = saved[6]
