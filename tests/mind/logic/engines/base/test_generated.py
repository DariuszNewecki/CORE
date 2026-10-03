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


from mind.logic.engines.base import extract_line_number


# ID: ab32f381-1451-431d-bd7e-8a86a41e558d
def test_extract_line_number():
    # Canonical structured key takes precedence.
    assert extract_line_number("any message", {"line_number": 42}) == 42

    # Short alias used by legacy sensors.
    assert extract_line_number("any message", {"line": 7}) == 7

    # String digits are coerced.
    assert extract_line_number("any message", {"line_number": "99"}) == 99

    # Regex fallback extracts embedded "Line N".
    assert extract_line_number("Violation at Line 15 in foo.py") == 15

    # Case-insensitive lowercase variant.
    assert extract_line_number("found at line 23") == 23

    # No line info available.
    assert extract_line_number("no line here", None) is None

    # Zero / negative values fall through to None.
    assert extract_line_number("nothing", {"line_number": 0}) is None


from mind.logic.engines.base import normalize_violation


# ID: 35835f7e-c04d-444d-8172-7d94b0ec1d54
def test_normalize_violation() -> None:
    # String-shaped violation: returns (message, {})
    assert normalize_violation("bare message") == ("bare message", {})

    # Dict-shaped violation with message + details
    v = {"message": "struct message", "details": {"file": "x.py", "line": 3}}
    assert normalize_violation(v) == ("struct message", {"file": "x.py", "line": 3})

    # Dict-shaped violation without details: defaults to empty dict
    assert normalize_violation({"message": "no details"}) == ("no details", {})

    # Dict with explicit None details: coerced to empty dict
    assert normalize_violation({"message": "none details", "details": None}) == (
        "none details",
        {},
    )

    # Dict missing message: message coerced to empty string, details preserved
    assert normalize_violation({"details": {"k": 1}}) == ("", {"k": 1})


from mind.logic.engines.base import EngineResult


# ID: cad2aefb-5220-49cd-ac24-3386fd215f82
def test_EngineResult():
    result = EngineResult(
        ok=True,
        message="All constitutional checks passed",
        violations=[],
        engine_id="test_engine",
    )
    assert result.ok is True
    assert result.message == "All constitutional checks passed"
    assert result.violations == []
    assert result.engine_id == "test_engine"
    assert result.extra == {}


from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
# ID: 7ae71fb7-d1b7-48d1-8ece-e402a6b6febc
async def test_BaseEngine_verify():
    # Arrange
    engine = MagicMock(spec=BaseEngine)
    engine.verify = AsyncMock(return_value=MagicMock())

    file_path = Path("/tmp/audit_target.py")
    params = {"rule": "no_todo_comments"}

    # Act
    result = await engine.verify(file_path, params)

    # Assert
    engine.verify.assert_awaited_once_with(file_path, params)
    assert result is not None
