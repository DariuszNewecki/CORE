from __future__ import annotations

import ast

from mind.logic.engines.ast_gate.checks.generic_checks import GenericASTChecks


# ID: 1de482ab-1847-4250-9772-ad31c5c4ac0e
def test_validate_requirement() -> None:
    source = "def foo() -> int:\n    return 1\n"
    tree = ast.parse(source)
    func_node = tree.body[0]

    # returns_type: matching return annotation -> no error
    assert (
        GenericASTChecks.validate_requirement(
            func_node, {"check_type": "returns_type", "expected": "int"}
        )
        is None
    )

    # returns_type: mismatched return annotation -> error string
    mismatch = GenericASTChecks.validate_requirement(
        func_node, {"check_type": "returns_type", "expected": "str"}
    )
    assert mismatch is not None
    assert "expected '-> str'" in mismatch

    # forbidden_calls: clean function -> None
    assert (
        GenericASTChecks.validate_requirement(
            func_node, {"check_type": "forbidden_calls", "calls": ["print"]}
        )
        is None
    )

    # forbidden_imports: clean function -> None
    assert (
        GenericASTChecks.validate_requirement(
            func_node, {"check_type": "forbidden_imports", "imports": ["click"]}
        )
        is None
    )

    # decorator_args: absent decorator -> None
    assert (
        GenericASTChecks.validate_requirement(
            func_node,
            {
                "check_type": "decorator_args",
                "decorator": "atomic_action",
                "required_kwargs": ["action_id"],
            },
        )
        is None
    )


from unittest.mock import patch


# ID: 2cfb5ffe-0c5f-47e1-af2c-21585227c2ac
def test_GenericASTChecks_is_selected():
    empty_selector_node = ast.parse("x = 1").body[0]
    assert GenericASTChecks.is_selected(empty_selector_node, {}) is True

    decorated = ast.parse("@my.decorator\ndef f():\n    pass\n").body[0]
    with patch(
        "mind.logic.engines.ast_gate.checks.generic_checks.ASTHelpers.full_attr_name",
        return_value="my.decorator",
    ):
        assert (
            GenericASTChecks.is_selected(decorated, {"has_decorator": "my.decorator"})
            is True
        )

    func = ast.parse("def foobar():\n    pass\n").body[0]
    assert GenericASTChecks.is_selected(func, {"name_regex": "^foo"}) is True
    assert GenericASTChecks.is_selected(func, {"name_regex": "^bar"}) is False

    cls = ast.parse("class Child(Base):\n    pass\n").body[0]
    with patch(
        "mind.logic.engines.ast_gate.checks.generic_checks.ASTHelpers.full_attr_name",
        return_value="Base",
    ):
        assert GenericASTChecks.is_selected(cls, {"inherits_from": "Base"}) is True
