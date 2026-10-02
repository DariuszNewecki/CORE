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


import asyncio
from pathlib import Path
from typing import Any


# ID: 05259c4f-e808-4234-b65b-f161cf2d6ee9
def test_BaseEngine() -> None:
    class _ConcreteEngine(BaseEngine):
        _context_check_types = frozenset({"cli", "contracts"})

        # ID: e8a0a2e7-0374-409b-ac2f-4539ae337ec5
        async def verify(self, file_path: Path, params: dict[str, Any]) -> str:
            return "ok"

    engine = _ConcreteEngine()

    # Default class-level metadata inherited from the ABC.
    assert BaseEngine._always_context_level is False
    assert isinstance(_ConcreteEngine._context_check_types, frozenset)

    # is_context_level_for is dispatched on the class without instantiation.
    assert _ConcreteEngine.is_context_level_for("cli") is True
    assert _ConcreteEngine.is_context_level_for("contracts") is True

    # Happy path: abstract verify method is implemented and awaitable.
    result = asyncio.run(engine.verify(Path("/tmp/example.py"), {}))
    assert result == "ok"
