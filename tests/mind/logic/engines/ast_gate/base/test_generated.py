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
