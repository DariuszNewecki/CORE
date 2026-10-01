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
