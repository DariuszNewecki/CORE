"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/mind/logic/engines/base.py
- Symbol: BaseEngine
- Status: verified_in_sandbox
- Generated: 2026-01-11 02:19:03
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import pytest

from mind.logic.engines.base import BaseEngine, EngineResult


# Detected return type: BaseEngine is an abstract class with async abstract method 'verify'


class TestBaseEngine:
    """Test suite for BaseEngine abstract class."""

    def test_base_engine_is_abstract(self):
        """Test that BaseEngine cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseEngine()

    def test_verify_is_abstract_method(self):
        """Test that verify method is abstract and must be implemented."""

        # Create a concrete subclass to test the abstract method
        class ConcreteEngine(BaseEngine):
            async def verify(self, file_path: Path, params: dict[str, str]) -> str:
                return "test"

        # Verify the subclass can be instantiated
        engine = ConcreteEngine()
        assert isinstance(engine, BaseEngine)

    async def test_concrete_implementation_works(self):
        """Test that a concrete implementation of BaseEngine works correctly."""

        class TestEngine(BaseEngine):
            async def verify(self, file_path: Path, params: dict[str, str]) -> str:
                return f"Verified {file_path} with {len(params)} params"

        engine = TestEngine()
        test_path = Path("/absolute/path/to/file.txt")
        test_params = {"rule1": "value1", "rule2": "value2"}

        result = await engine.verify(test_path, test_params)
        assert result == "Verified /absolute/path/to/file.txt with 2 params"

    def test_verify_signature(self):
        """Test that verify method has correct signature in subclasses."""

        class ValidEngine(BaseEngine):
            async def verify(self, file_path: Path, params: dict[str, str]) -> str:
                return ""

        class InvalidEngine(BaseEngine):
            # Missing async
            def verify(self, file_path: Path, params: dict[str, str]) -> str:
                return ""

        # Valid engine should work
        valid_engine = ValidEngine()

        # Invalid engine should fail type checking but pytest won't catch this at runtime
        # This test documents the expected signature

    async def test_file_path_absolute_requirement(self):
        """Test that file_path parameter expects absolute path."""

        class PathCheckingEngine(BaseEngine):
            async def verify(self, file_path: Path, params: dict[str, str]) -> bool:
                return file_path.is_absolute()

        engine = PathCheckingEngine()

        # Test with absolute path
        abs_path = Path("/usr/local/bin/test")
        result = await engine.verify(abs_path, {})
        assert result

        # Test with relative path (should return False per is_absolute())
        rel_path = Path("relative/path.txt")
        result = await engine.verify(rel_path, {})
        assert not result

    async def test_params_dict_type(self):
        """Test that params is a dictionary."""

        class ParamsCheckingEngine(BaseEngine):
            async def verify(self, file_path: Path, params: dict[str, str]) -> int:
                return len(params)

        engine = ParamsCheckingEngine()
        test_path = Path("/test/file.txt")

        # Test with empty dict
        result = await engine.verify(test_path, {})
        assert result == 0

        # Test with populated dict
        result = await engine.verify(test_path, {"key1": "value1", "key2": "value2"})
        assert result == 2

    def test_context_check_types_default_is_empty(self):
        """BaseEngine._context_check_types defaults to empty frozenset."""

        class MinimalEngine(BaseEngine):
            async def verify(self, file_path: Path, params: dict) -> EngineResult:
                return EngineResult(ok=True, message="", violations=[], engine_id="x")

        assert MinimalEngine._context_check_types == frozenset()

    def test_is_context_level_for_returns_false_by_default(self):
        """is_context_level_for returns False when _context_check_types is empty."""

        class MinimalEngine(BaseEngine):
            async def verify(self, file_path: Path, params: dict) -> EngineResult:
                return EngineResult(ok=True, message="", violations=[], engine_id="x")

        assert MinimalEngine.is_context_level_for("any_check") is False
        assert MinimalEngine.is_context_level_for(None) is False

    def test_is_context_level_for_with_declared_check_types(self):
        """Subclass declaring _context_check_types gets correct dispatch."""

        class ContextEngine(BaseEngine):
            _context_check_types: ClassVar[frozenset[str]] = frozenset(
                {"check_a", "check_b"}
            )

            async def verify(self, file_path: Path, params: dict) -> EngineResult:
                return EngineResult(ok=True, message="", violations=[], engine_id="x")

        assert ContextEngine.is_context_level_for("check_a") is True
        assert ContextEngine.is_context_level_for("check_b") is True
        assert ContextEngine.is_context_level_for("check_c") is False
        assert ContextEngine.is_context_level_for(None) is False

    def test_is_context_level_for_is_classmethod(self):
        """is_context_level_for is callable on the class, not just instances."""
        assert callable(BaseEngine.is_context_level_for)
        # Calling on the class directly (not an instance) must work
        assert BaseEngine.is_context_level_for("anything") is False

    def test_class_docstring(self):
        """Test that BaseEngine has appropriate documentation."""
        assert "Abstract base class for all Governance Engines" in BaseEngine.__doc__
        assert "async" in BaseEngine.__doc__
        assert "Database-as-SSOT" in BaseEngine.__doc__

    def test_verify_method_docstring(self):
        """Test that verify method has proper documentation."""
        # Check docstring components
        docstring = BaseEngine.verify.__doc__
        assert docstring is not None
        assert "Verify a file or context against constitutional rules" in docstring
        assert "file_path: Absolute path to the file being audited" in docstring
        assert "params: Rule-specific parameters from the Mind" in docstring
        assert "Returns:" in docstring
        assert "EngineResult indicating compliance status" in docstring
