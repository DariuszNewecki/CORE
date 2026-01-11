"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/shared/ast_utility.py
- Symbol: extract_base_classes
- Status: verified_in_sandbox
- Generated: 2026-01-11 01:10:04
"""

import pytest
from shared.ast_utility import extract_base_classes
import ast

# Detected return type: list[str]

def test_extract_base_classes_single_name_base():
    """Test with a single base class using a simple Name."""
    code = "class MyClass(BaseClass): pass"
    tree = ast.parse(code)
    class_node = tree.body[0]
    result = extract_base_classes(class_node)
    assert result == ["BaseClass"]

def test_extract_base_classes_multiple_name_bases():
    """Test with multiple base classes using simple Names."""
    code = "class MyClass(BaseOne, BaseTwo, BaseThree): pass"
    tree = ast.parse(code)
    class_node = tree.body[0]
    result = extract_base_classes(class_node)
    assert result == ["BaseOne", "BaseTwo", "BaseThree"]

def test_extract_base_classes_attribute_base_simple():
    """Test with a base class using a simple Attribute (e.g., module.Class)."""
    code = "class MyClass(mod.ClassName): pass"
    tree = ast.parse(code)
    class_node = tree.body[0]
    result = extract_base_classes(class_node)
    # base.value is ast.Name 'mod', base.attr is 'ClassName'
    assert result == ["mod.ClassName"]

def test_extract_base_classes_attribute_base_nested():
    """Test with a base class using a nested Attribute (e.g., mod.submod.Class)."""
    code = "class MyClass(mod.sub.ClassName): pass"
    tree = ast.parse(code)
    class_node = tree.body[0]
    result = extract_base_classes(class_node)
    # base.value is an ast.Attribute (mod.sub), base.attr is 'ClassName'
    # The function captures the last attribute segment of base.value ('sub')
    assert result == ["sub.ClassName"]

def test_extract_base_classes_mixed_bases():
    """Test with a mix of Name and Attribute base classes."""
    code = "class MyClass(BaseOne, pkg.ModuleClass, mod.sub.DeepClass): pass"
    tree = ast.parse(code)
    class_node = tree.body[0]
    result = extract_base_classes(class_node)
    assert result == ["BaseOne", "pkg.ModuleClass", "sub.DeepClass"]

def test_extract_base_classes_no_bases():
    """Test a class with no explicit base classes."""
    code = "class MyClass: pass"
    tree = ast.parse(code)
    class_node = tree.body[0]
    result = extract_base_classes(class_node)
    assert result == []

def test_extract_base_classes_complex_expression_ignored():
    """Test that complex base expressions (e.g., Call, Subscript) are ignored."""
    code = "class MyClass(metaclass=ABCMeta): pass"
    tree = ast.parse(code)
    class_node = tree.body[0]
    # The base list is empty, keywords contain the metaclass.
    result = extract_base_classes(class_node)
    assert result == []
