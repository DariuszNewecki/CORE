"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/mind/logic/engines/registry.py
- Symbol: EngineRegistry
- Status: verified_in_sandbox
- Generated: 2026-01-11 02:21:23
"""

import pytest

from mind.logic.engines.registry import EngineRegistry


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
    """Test that all hardcoded engine IDs can be retrieved without error."""
    EngineRegistry._instances.clear()
    supported_ids = [
        "ast_gate",
        "glob_gate",
        "action_gate",
        "regex_gate",
        "workflow_gate",
        "knowledge_gate",
        "llm_gate",
    ]
    for engine_id in supported_ids:
        instance = EngineRegistry.get(engine_id)
        assert instance is not None
        assert engine_id in EngineRegistry._instances
        assert EngineRegistry._instances[engine_id] == instance
