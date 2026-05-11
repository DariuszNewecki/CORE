"""Comprehensive pytest tests for src/body/atomic/modularity_fix.py."""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.body.atomic.modularity_fix import (
    _SymbolInventory,
    _check_decorator_conservation,
    _collect_preserved_decorators,
    _decorator_simple_name,
    _detect_layer_from_path,
    _extract_symbol_inventory,
    _find_callers,
    _find_worst_modularity_violator,
    _invalidate_split_pycache,
    _load_split_confidence_threshold,
    _validate_plan_against_inventory,
    action_fix_modularity,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_source() -> str:
    return """
import os
from typing import List

CONSTANT_VALUE = 42

def top_func():
    pass

class MyClass:
    def method_one(self):
        pass

    def method_two(self):
        pass

    class_level_attr = "value"
"""


@pytest.fixture
def empty_inventory() -> _SymbolInventory:
    return _SymbolInventory()


@pytest.fixture
def populated_inventory() -> _SymbolInventory:
    return _SymbolInventory(
        classes=["MyClass"],
        functions=["top_func"],
        constants=["CONSTANT_VALUE"],
        dominant_class="MyClass",
        dominant_methods=["method_one", "method_two"],
        dominant_class_assigns=["class_level_attr"],
        imported=[("os", "os"), ("List", "typing.List")],
    )


@pytest.fixture
def temp_repo(tmp_path: Path) -> Path:
    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True)
    return tmp_path


# ---------------------------------------------------------------------------
# _SymbolInventory tests
# ---------------------------------------------------------------------------

class TestSymbolInventory:
    """Tests for _SymbolInventory dataclass and its methods."""

    def test_defined_top_level_names_empty(self, empty_inventory: _SymbolInventory) -> None:
        assert empty_inventory.defined_top_level_names() == set()

    def test_defined_top_level_names_populated(self, populated_inventory: _SymbolInventory) -> None:
        expected = {"MyClass", "top_func", "CONSTANT_VALUE"}
        assert populated_inventory.defined_top_level_names() == expected

    def test_defined_class_member_names_empty(self, empty_inventory: _SymbolInventory) -> None:
        assert empty_inventory.defined_class_member_names() == set()

    def test_defined_class_member_names_populated(self, populated_inventory: _SymbolInventory) -> None:
        expected = {"method_one", "method_two", "class_level_attr"}
        assert populated_inventory.defined_class_member_names() == expected

    def test_imported_lookup_empty(self, empty_inventory: _SymbolInventory) -> None:
        assert empty_inventory.imported_lookup() == {}

    def test_imported_lookup_populated(self, populated_inventory: _SymbolInventory) -> None:
        expected = {"os": "os", "List": "typing.List"}
        assert populated_inventory.imported_lookup() == expected

    def test_render_for_prompt_empty(self, empty_inventory: _SymbolInventory) -> None:
        result = empty_inventory.render_for_prompt()
        assert "(file could not be parsed" in result

    def test_render_for_prompt_populated(self, populated_inventory: _SymbolInventory) -> None:
        result = populated_inventory.render_for_prompt()
        assert "Defined here:" in result
        assert "MyClass" in result
        assert "top_func" in result
        assert "CONSTANT_VALUE" in result
        assert "method_one" in result
        assert "method_two" in result
        assert "class_level_attr" in result
        assert "Imported" in result
        assert "os (from os)" in result
        assert "List (from typing.List)" in result

    def test_render_for_prompt_no_imports(self) -> None:
        inv = _SymbolInventory(classes=["A"], functions=["f"], constants=["C"])
        result = inv.render_for_prompt()
        assert "Imported" not in res
