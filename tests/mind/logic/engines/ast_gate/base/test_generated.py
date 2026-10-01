from __future__ import annotations

import ast

from mind.logic.engines.ast_gate.base import ASTHelpers


# ID: 3351c2f3-44a1-4e97-8ed9-bff133bb9f75
def test_ASTHelpers_is_type_checking_condition() -> None:
    # Happy path: bare TYPE_CHECKING name
    name_node = ast.parse("if TYPE_CHECKING: pass").body[0].test
    assert ASTHelpers.is_type_checking_condition(name_node) is True

    # Happy path: typing.TYPE_CHECKING attribute
    attr_node = ast.parse("if typing.TYPE_CHECKING: pass").body[0].test
    assert ASTHelpers.is_type_checking_condition(attr_node) is True

    # Negative: unrelated name
    other_node = ast.parse("if DEBUG: pass").body[0].test
    assert ASTHelpers.is_type_checking_condition(other_node) is False

    # Negative: non-typing attribute with TYPE_CHECKING attr
    wrong_attr = ast.parse("if foo.TYPE_CHECKING: pass").body[0].test
    assert ASTHelpers.is_type_checking_condition(wrong_attr) is False


# ID: 40ef5669-5310-4c6f-a4b4-6dfb8c16bc39
def test_domain_matches():
    # Exact match
    assert ASTHelpers.domain_matches("billing", ["billing"]) is True

    # Prefix match via subdomain
    assert ASTHelpers.domain_matches("billing.core", ["billing"]) is True
    assert ASTHelpers.domain_matches("billing.core.deep", ["billing"]) is True

    # Matches one of several allowed domains
    assert ASTHelpers.domain_matches("orders", ["billing", "orders"]) is True

    # Non-matching domain
    assert ASTHelpers.domain_matches("inventory", ["billing", "orders"]) is False

    # Partial prefix that is not a proper subdomain boundary
    assert ASTHelpers.domain_matches("billingx", ["billing"]) is False

    # Empty inputs
    assert ASTHelpers.domain_matches("", ["billing"]) is False
    assert ASTHelpers.domain_matches("billing", []) is False


from pathlib import Path


# ID: 464a57b7-ddf7-4cdf-9264-96564cf82b55
def test_ASTHelpers_extract_domain_from_path():
    assert (
        ASTHelpers.extract_domain_from_path("src/mind/governance/auditor.py")
        == "mind.governance"
    )
    assert (
        ASTHelpers.extract_domain_from_path(
            Path("project/src/mind/governance/auditor.py")
        )
        == "mind.governance"
    )
    assert ASTHelpers.extract_domain_from_path("top_level.py") == ""


# ID: 38d999a6-ef72-4da7-b705-80b1ec8ef1a7
def test_ASTHelpers_iter_module_level_stmts() -> None:
    source = "import os\nx = 1\ndef foo():\n    pass\n"
    tree = ast.parse(source)

    result = list(ASTHelpers.iter_module_level_stmts(tree))

    assert result == tree.body
    assert len(result) == 3
    assert isinstance(result[0], ast.Import)
    assert isinstance(result[1], ast.Assign)
    assert isinstance(result[2], ast.FunctionDef)


# ID: 28400feb-05d0-4cf1-a019-cc461ec73bd6
def test_ASTHelpers_iter_module_level_stmts_non_module() -> None:
    expr = ast.parse("1 + 1", mode="eval")

    result = list(ASTHelpers.iter_module_level_stmts(expr))

    assert result == []


# ID: dcde8f95-7853-467b-8a75-57a5ac2aed1d
def test_ASTHelpers_matches_call():
    # Happy path: exact match
    assert ASTHelpers.matches_call("asyncio.run", ["asyncio.run"]) is True

    # Happy path: suffix match with dot boundary
    assert ASTHelpers.matches_call("foo.asyncio.run", ["asyncio.run"]) is True

    # No false positive on bare leaf name
    assert ASTHelpers.matches_call("subprocess.run", ["asyncio.run"]) is False

    # No match against empty disallowed list
    assert ASTHelpers.matches_call("asyncio.run", []) is False

    # Multiple patterns, one matching
    assert (
        ASTHelpers.matches_call("os.system", ["subprocess.call", "os.system"]) is True
    )


# ID: fc3cf569-b2a6-4aac-ab52-1e467dabe9a6
def test_ASTHelpers_walk_module_stmt_without_nested_scopes():
    source = """
x = 1
# ID: e829e076-a33b-450e-abfa-0031d43bbd45
def foo():
    y = 2
    return y
z = 3
"""
    module = ast.parse(source)
    stmt = module.body[0]
    result = list(ASTHelpers.walk_module_stmt_without_nested_scopes(stmt))
    assert stmt in result
    for node in result:
        assert isinstance(node, ast.AST)


from unittest.mock import patch


# ID: c805dc30-434a-42b4-99d0-8e31e995d79d
def test_ASTHelpers_resolve_qualified_name() -> None:
    node = ast.parse("path.exists", mode="eval").body
    alias_map = {"path": "os.path"}

    with patch.object(
        ASTHelpers, "full_attr_name", return_value="path.exists"
    ) as mock_full_attr_name:
        result = ASTHelpers.resolve_qualified_name(node, alias_map)

    mock_full_attr_name.assert_called_once_with(node)
    assert result == "os.path.exists"


# ID: 93246e15-71a4-4347-8a89-2b95b775e604
def test_ASTHelpers_build_import_alias_map() -> None:
    source = (
        "from os import replace\n"
        "from os import replace as r\n"
        "import os\n"
        "import os.path as op\n"
        "def f():\n"
        "    from sys import exit as ex\n"
    )
    tree = ast.parse(source)
    result = ASTHelpers.build_import_alias_map(tree)

    assert result["replace"] == "os.replace"
    assert result["r"] == "os.replace"
    assert result["os"] == "os"
    assert result["op"] == "os.path"
    assert result["ex"] == "sys.exit"


# ID: ee6697a7-2b84-4cc6-9cb2-4be8d499959a
def test_ASTHelpers_full_attr_name():
    # ast.Name -> simple identifier
    name_node = ast.Name(id="create_async_engine", ctx=ast.Load())
    assert ASTHelpers.full_attr_name(name_node) == "create_async_engine"

    # ast.Attribute -> dotted chain (asyncio.run)
    attr_node = ast.Attribute(
        value=ast.Name(id="asyncio", ctx=ast.Load()),
        attr="run",
        ctx=ast.Load(),
    )
    assert ASTHelpers.full_attr_name(attr_node) == "asyncio.run"

    # nested attribute (loop.create_task)
    nested_node = ast.Attribute(
        value=ast.Name(id="loop", ctx=ast.Load()),
        attr="create_task",
        ctx=ast.Load(),
    )
    assert ASTHelpers.full_attr_name(nested_node) == "loop.create_task"

    # non-name/non-attribute node -> None
    const_node = ast.Constant(value=42)
    assert ASTHelpers.full_attr_name(const_node) is None


# ID: 206ec107-9553-40da-acc7-182dd2355cc4
def test_ASTHelpers_lineno():
    node = ast.parse("x = 1").body[0]
    result = ASTHelpers.lineno(node)
    assert result == node.lineno
    assert isinstance(result, int)




# ID: 5c7e6f13-d65d-476d-9e8d-f45e9efde8db
def test_ASTHelpers_domain_matches():
    assert (
        ASTHelpers.domain_matches("api.example.com", ["api.example.com", "other.com"])
        is True
    )
