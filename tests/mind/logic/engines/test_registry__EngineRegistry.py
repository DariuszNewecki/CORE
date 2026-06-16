"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/mind/logic/engines/registry.py
- Symbol: EngineRegistry
- Status: verified_in_sandbox
- Generated: 2026-01-11 02:21:23
"""

from pathlib import Path

import pytest

from mind.logic.engines.registry import EngineRegistry
from shared.path_resolver import PathResolver


@pytest.fixture(autouse=True)
def _initialize_registry():
    """Ensure the registry is initialized for every test in this module.

    The class-level state survives across tests in the same process, so an
    early initialization (here or via cross-module side effect) is what
    lets ``get()`` succeed. Doing it explicitly makes standalone runs of
    this file work without depending on test-order coincidence.
    """
    EngineRegistry.initialize(PathResolver(repo_root=Path("/opt/dev/CORE")))


# Detected return type: The 'get' method returns an instance of the requested engine class (Any).


def test_get_returns_cached_instance():
    """Test that get returns the same instance on subsequent calls."""
    # Clear any existing instances to ensure test isolation
    EngineRegistry._instances.clear()
    instance1 = EngineRegistry.get("ast_gate")
    instance2 = EngineRegistry.get("ast_gate")
    assert instance1 == instance2
    assert instance1 is instance2


def test_get_raises_valueerror_for_unknown_engine():
    """Test that get raises ValueError for an unsupported engine ID."""
    EngineRegistry._instances.clear()
    with pytest.raises(
        ValueError, match="Unsupported Governance Engine: unknown_engine"
    ):
        EngineRegistry.get("unknown_engine")


def test_get_registers_different_engines():
    """Test that different engine IDs return different engine instances."""
    EngineRegistry._instances.clear()
    ast_instance = EngineRegistry.get("ast_gate")
    glob_instance = EngineRegistry.get("glob_gate")
    assert ast_instance != glob_instance
    assert "ast_gate" in EngineRegistry._instances
    assert "glob_gate" in EngineRegistry._instances
    assert EngineRegistry._instances["ast_gate"] == ast_instance
    assert EngineRegistry._instances["glob_gate"] == glob_instance


def test_get_all_supported_engines():
    """Test that all hardcoded engine IDs can be retrieved without error.

    ``llm_gate`` is excluded — when no LLM client is wired into the
    registry, ``get('llm_gate')`` returns an uncached ``LLMGateStubEngine``
    (see registry.get's llm_client branch), so the
    ``engine_id in _instances`` assertion does not apply. That code path
    is covered by other tests; the rest of the engines follow the
    standard JIT-instance-cache pattern.
    """
    EngineRegistry._instances.clear()
    supported_ids = [
        "ast_gate",
        "glob_gate",
        "action_gate",
        "regex_gate",
        "workflow_gate",
        "knowledge_gate",
    ]
    for engine_id in supported_ids:
        instance = EngineRegistry.get(engine_id)
        assert instance is not None
        assert engine_id in EngineRegistry._instances
        assert EngineRegistry._instances[engine_id] == instance


def test_engine_source_files_lists_registered_engine_modules():
    """engine_source_files() returns repo-relative POSIX source paths for every
    registered engine, derived from class modules (not a hardcoded dir).

    Consumed by the assisted lane to detect a self-referential fix — a diff
    that patches an audit engine cannot be validated by the in-process auditor
    (#661).
    """
    files = EngineRegistry.engine_source_files()
    assert files, "registry must expose at least one engine source file"
    # The orphan/duplication detector that surfaced #661 must be in the set.
    assert "src/mind/logic/engines/knowledge_gate.py" in files
    # Every entry is a repo-relative .py path under the engines package.
    for path in files:
        assert path.startswith("src/mind/logic/engines/")
        assert path.endswith(".py")


def test_initialize_clears_engine_class_cache_and_rediscovers():
    """initialize() MUST clear ``_engine_classes`` AND reset ``_discovered``
    so engine modules added between calls become visible.

    Regression: ADR-079 Slice B shipped ``taxonomy_gate`` against a
    long-running core-api process. The auditor's per-run re-initialize
    pattern (auditor.py:99-102) was meant to refresh state, but
    ``initialize()`` only cleared ``_instances`` — the previously-cached
    ``_engine_classes`` dict and ``_discovered=True`` flag persisted, so
    the new engine module was never imported. Audit reported
    "Unsupported Governance Engine: taxonomy_gate" until manual restart.

    This test simulates the same shape: corrupt the cache (remove an
    entry), re-initialize, assert the entry is back without a process
    restart.
    """
    assert "ast_gate" in EngineRegistry._engine_classes

    # Simulate the stale-cache shape — entry missing from _engine_classes
    # (as it would be if a new engine were added after first discovery).
    cached_cls = EngineRegistry._engine_classes.pop("ast_gate")
    assert "ast_gate" not in EngineRegistry._engine_classes

    # Re-initialize: the fix must restore the entry via fresh discovery.
    EngineRegistry.initialize(PathResolver(repo_root=Path("/opt/dev/CORE")))
    assert "ast_gate" in EngineRegistry._engine_classes
    assert EngineRegistry._engine_classes["ast_gate"] is cached_cls


def test_initialize_clears_instance_cache():
    """initialize() must also clear ``_instances`` so re-init's per-process
    state (e.g. swapped llm_client) is reflected on next ``get()``."""
    EngineRegistry.get("ast_gate")
    assert "ast_gate" in EngineRegistry._instances

    EngineRegistry.initialize(PathResolver(repo_root=Path("/opt/dev/CORE")))
    assert EngineRegistry._instances == {}
