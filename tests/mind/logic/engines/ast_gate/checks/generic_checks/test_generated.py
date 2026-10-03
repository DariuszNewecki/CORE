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


# ID: 84929fc4-8011-49a4-a28f-53b63399c185
def test_GenericASTChecks():
    # is_selected: empty selector -> True
    node = ast.parse("x = 1").body[0]
    assert GenericASTChecks.is_selected(node, {}) is True

    # is_selected: name_regex match
    func = ast.parse("def my_thing():\n    pass\n").body[0]
    assert GenericASTChecks.is_selected(func, {"name_regex": r"^my_"}) is True
    assert GenericASTChecks.is_selected(func, {"name_regex": r"^other_"}) is False

    # is_selected: inherits_from
    cls = ast.parse("class Foo(Base):\n    pass\n").body[0]
    assert GenericASTChecks.is_selected(cls, {"inherits_from": "Base"}) is True
    assert GenericASTChecks.is_selected(cls, {"inherits_from": "Other"}) is False

    # is_selected: has_decorator
    dec_func = ast.parse("@my_decorator\ndef f():\n    pass\n").body[0]
    assert (
        GenericASTChecks.is_selected(dec_func, {"has_decorator": "my_decorator"})
        is True
    )
    assert (
        GenericASTChecks.is_selected(dec_func, {"has_decorator": "not_here"}) is False
    )

    # validate_requirement: returns_type mismatch
    plain = ast.parse("def f():\n    return 1\n").body[0]
    err = GenericASTChecks.validate_requirement(
        plain, {"check_type": "returns_type", "expected": "ActionResult"}
    )
    assert err is not None
    assert "ActionResult" in err

    # validate_requirement: forbidden_calls detection
    printer = ast.parse("def f():\n    print(1)\n").body[0]
    err = GenericASTChecks.validate_requirement(
        printer, {"check_type": "forbidden_calls", "calls": ["print"]}
    )
    assert err is not None and "print" in err

    # validate_requirement: forbidden_imports detection
    importer = ast.parse("import rich\n").body[0]
    err = GenericASTChecks.validate_requirement(
        importer, {"check_type": "forbidden_imports", "imports": ["rich"]}
    )
    assert err is not None and "rich" in err

    # validate_requirement: decorator_args missing kwarg
    dec = ast.parse("@atomic_action\ndef f():\n    pass\n").body[0]
    err = GenericASTChecks.validate_requirement(
        dec,
        {
            "check_type": "decorator_args",
            "decorator": "atomic_action",
            "required_kwargs": ["action_id"],
        },
    )
    assert err is not None and "action_id" in err

    # happy path: valid returns type -> None
    good = ast.parse("def f() -> ActionResult:\n    return ActionResult()\n").body[0]
    assert (
        GenericASTChecks.validate_requirement(
            good, {"check_type": "returns_type", "expected": "ActionResult"}
        )
        is None
    )


# ID: fd9dfe1d-b181-4e19-beaa-bb727b3733de
def test_GenericASTChecks_validate_requirement():
    from mind.logic.engines.ast_gate.checks.generic_checks import GenericASTChecks

    # Happy path: a function that satisfies the "returns_type" requirement.
    source = "def foo() -> ActionResult:\n    return None\n"
    tree = ast.parse(source)
    func_node = tree.body[0]
    assert isinstance(func_node, ast.FunctionDef)

    requirement = {"check_type": "returns_type", "expected": "ActionResult"}

    with patch(
        "mind.logic.engines.ast_gate.checks.generic_checks.ASTHelpers.full_attr_name",
        return_value="ActionResult",
    ) as mock_attr:
        result = GenericASTChecks.validate_requirement(func_node, requirement)

    assert result is None
    mock_attr.assert_called_with(func_node.returns)
