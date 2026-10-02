from __future__ import annotations

from mind.logic.engines.base import BaseEngine


# ID: 768ba8ec-abb7-4ca3-928d-d64bda98ac45
def test_BaseEngine_is_context_level_for():
    # ID: a38f67a1-afe4-4790-a021-1fb1da8f2675
    class AlwaysEngine(BaseEngine):
        _always_context_level = True
        _context_check_types: frozenset[str] = frozenset()

    # ID: a2ee604f-066d-4308-a24a-19e2c618ef7a
    class NamedEngine(BaseEngine):
        _always_context_level = False
        _context_check_types = frozenset({"cli_gate", "contracts_gate", "runtime_gate"})

    # ID: e9c04a52-f6ce-4704-95cc-dc71d16540c1
    class DefaultEngine(BaseEngine):
        _always_context_level = False
        _context_check_types = frozenset()

    assert AlwaysEngine.is_context_level_for("anything") is True
    assert AlwaysEngine.is_context_level_for(None) is True

    assert NamedEngine.is_context_level_for("cli_gate") is True
    assert NamedEngine.is_context_level_for("contracts_gate") is True
    assert NamedEngine.is_context_level_for("runtime_gate") is True
    assert NamedEngine.is_context_level_for("some_other") is False
    assert NamedEngine.is_context_level_for(None) is False

    assert DefaultEngine.is_context_level_for("cli_gate") is False
    assert DefaultEngine.is_context_level_for(None) is False
