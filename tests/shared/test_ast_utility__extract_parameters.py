"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/shared/ast_utility.py
- Symbol: extract_parameters
- Status: verified_in_sandbox
- Generated: 2026-01-11 01:10:22
"""

import ast

from shared.ast_utility import extract_parameters


# Detected return type: list[str]


def test_extract_parameters_normal_function():
    source = "def my_func(a, b, c): pass"
    tree = ast.parse(source)
    func_node = tree.body[0]
    result = extract_parameters(func_node)
    assert result == ["a", "b", "c"]


def test_extract_parameters_async_function():
    source = "async def my_async_func(x, y): pass"
    tree = ast.parse(source)
    func_node = tree.body[0]
    result = extract_parameters(func_node)
    assert result == ["x", "y"]


def test_extract_parameters_no_parameters():
    source = "def func(): pass"
    tree = ast.parse(source)
    func_node = tree.body[0]
    result = extract_parameters(func_node)
    assert result == []


def test_extract_parameters_only_args():
    source = "def func(*args): pass"
    tree = ast.parse(source)
    func_node = tree.body[0]
    result = extract_parameters(func_node)
    assert result == []


def test_extract_parameters_only_kwargs():
    source = "def func(**kwargs): pass"
    tree = ast.parse(source)
    func_node = tree.body[0]
    result = extract_parameters(func_node)
    assert result == []


def test_extract_parameters_mixed_pos_and_starred():
    source = "def func(a, b, *args, c=1, **kwargs): pass"
    tree = ast.parse(source)
    func_node = tree.body[0]
    result = extract_parameters(func_node)
    assert result == ["a", "b"]


def test_extract_parameters_with_defaults():
    source = "def func(a, b=10, c='hello'): pass"
    tree = ast.parse(source)
    func_node = tree.body[0]
    result = extract_parameters(func_node)
    assert result == ["a", "b", "c"]


def test_extract_parameters_raises_error_on_non_function_node():
    source = "x = 5"
    tree = ast.parse(source)
    assign_node = tree.body[0]
    result = extract_parameters(assign_node)
    assert result == []


def test_extract_parameters_node_without_args_attribute():
    class FakeNode:
        pass

    fake_node = FakeNode()
    result = extract_parameters(fake_node)
    assert result == []


def test_extract_parameters_node_with_args_none():
    class FakeNode:
        args = None

    fake_node = FakeNode()
    result = extract_parameters(fake_node)
    assert result == []
