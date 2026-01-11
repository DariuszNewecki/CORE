"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/shared/ast_utility.py
- Symbol: FunctionCallVisitor
- Status: 9 tests passed, some failed
- Passing tests: test_function_call_visitor_initialization, test_visit_call_with_name_node, test_visit_call_with_attribute_node, test_multiple_calls_preserve_order_and_duplicates, test_nested_calls_are_recorded, test_method_chaining, test_empty_call_with_no_func, test_unique_calls_property_updates, test_visitor_continues_traversal
- Generated: 2026-01-11 01:11:10
"""

import ast

from shared.ast_utility import FunctionCallVisitor


def test_function_call_visitor_initialization():
    """Test that FunctionCallVisitor initializes with empty calls list."""
    visitor = FunctionCallVisitor()
    assert visitor.calls == []
    assert visitor._unique_calls == set()


def test_visit_call_with_name_node():
    """Test recording function calls with ast.Name nodes."""
    visitor = FunctionCallVisitor()
    node = ast.Call(func=ast.Name(id="foo", ctx=ast.Load()), args=[], keywords=[])
    visitor.visit_Call(node)
    assert visitor.calls == ["foo"]
    assert visitor._unique_calls == {"foo"}


def test_visit_call_with_attribute_node():
    """Test recording method calls with ast.Attribute nodes."""
    visitor = FunctionCallVisitor()
    node = ast.Call(
        func=ast.Attribute(
            value=ast.Name(id="obj", ctx=ast.Load()), attr="method", ctx=ast.Load()
        ),
        args=[],
        keywords=[],
    )
    visitor.visit_Call(node)
    assert visitor.calls == ["method"]
    assert visitor._unique_calls == {"method"}


def test_multiple_calls_preserve_order_and_duplicates():
    """Test that calls list preserves order and allows duplicates."""
    visitor = FunctionCallVisitor()
    call1 = ast.Call(func=ast.Name(id="func1", ctx=ast.Load()), args=[], keywords=[])
    call2 = ast.Call(func=ast.Name(id="func2", ctx=ast.Load()), args=[], keywords=[])
    call3 = ast.Call(func=ast.Name(id="func1", ctx=ast.Load()), args=[], keywords=[])
    visitor.visit_Call(call1)
    visitor.visit_Call(call2)
    visitor.visit_Call(call3)
    assert visitor.calls == ["func1", "func2", "func1"]
    assert visitor._unique_calls == {"func1", "func2"}


def test_nested_calls_are_recorded():
    """Test that nested function calls are all recorded."""
    visitor = FunctionCallVisitor()
    inner_call = ast.Call(
        func=ast.Name(id="inner", ctx=ast.Load()), args=[], keywords=[]
    )
    outer_call = ast.Call(
        func=ast.Name(id="outer", ctx=ast.Load()), args=[inner_call], keywords=[]
    )
    visitor.visit(outer_call)
    assert "inner" in visitor.calls
    assert "outer" in visitor.calls
    assert len(visitor.calls) == 2
    assert visitor._unique_calls == {"inner", "outer"}


def test_method_chaining():
    """Test recording method calls in chained expressions."""
    visitor = FunctionCallVisitor()
    method2_call = ast.Call(
        func=ast.Attribute(
            value=ast.Call(
                func=ast.Attribute(
                    value=ast.Name(id="obj", ctx=ast.Load()),
                    attr="method1",
                    ctx=ast.Load(),
                ),
                args=[],
                keywords=[],
            ),
            attr="method2",
            ctx=ast.Load(),
        ),
        args=[],
        keywords=[],
    )
    visitor.visit(method2_call)
    assert "method1" in visitor.calls
    assert "method2" in visitor.calls
    assert len(visitor.calls) == 2
    assert visitor._unique_calls == {"method1", "method2"}


def test_empty_call_with_no_func():
    """Test edge case - though unlikely in valid Python."""
    visitor = FunctionCallVisitor()
    node = ast.Call(func=None, args=[], keywords=[])
    visitor.visit_Call(node)
    assert visitor.calls == []


def test_unique_calls_property_updates():
    """Test that _unique_calls property updates when calls list changes."""
    visitor = FunctionCallVisitor()
    assert visitor._unique_calls == set()
    node = ast.Call(func=ast.Name(id="func", ctx=ast.Load()), args=[], keywords=[])
    visitor.visit_Call(node)
    assert visitor._unique_calls == {"func"}
    visitor.visit_Call(node)
    assert visitor._unique_calls == {"func"}
    node2 = ast.Call(func=ast.Name(id="func2", ctx=ast.Load()), args=[], keywords=[])
    visitor.visit_Call(node2)
    assert visitor._unique_calls == {"func", "func2"}


def test_visitor_continues_traversal():
    """Test that generic_visit is called to continue traversal."""
    visitor = FunctionCallVisitor()
    method_call = ast.Call(
        func=ast.Attribute(
            value=ast.Name(id="obj", ctx=ast.Load()), attr="method", ctx=ast.Load()
        ),
        args=[],
        keywords=[],
    )
    func2_call = ast.Call(
        func=ast.Name(id="func2", ctx=ast.Load()), args=[], keywords=[]
    )
    func1_call = ast.Call(
        func=ast.Name(id="func1", ctx=ast.Load()),
        args=[func2_call, method_call],
        keywords=[],
    )
    visitor.visit(func1_call)
    assert len(visitor.calls) == 3
    assert "func1" in visitor.calls
    assert "func2" in visitor.calls
    assert "method" in visitor.calls
    assert visitor._unique_calls == {"func1", "func2", "method"}
