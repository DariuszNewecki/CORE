from __future__ import annotations

import ast

from mind.logic.engines.ast_gate.checks.indeterminate_human_checks import (
    IndeterminateHumanChecks,
)


# ID: 5ab3e34d-26a0-40de-af58-c7cd785e9f3f
def test_IndeterminateHumanChecks():
    source = (
        "import sqlalchemy\n"
        "sqlalchemy.text(\"UPDATE core.blackboard_entries SET status = 'indeterminate' \"\n"
        '                "WHERE id = :id")\n'
    )
    tree = ast.parse(source)

    violations = IndeterminateHumanChecks.check_indeterminate_requires_human_mechanism(
        tree
    )

    assert isinstance(violations, list)
    assert len(violations) == 1
    assert "indeterminate" in violations[0]
    assert "resolution_mechanism = 'human'" in violations[0]

    compliant_source = (
        "import sqlalchemy\n"
        'sqlalchemy.text("UPDATE core.blackboard_entries "\n'
        "                \"SET status = 'indeterminate', resolution_mechanism = 'human' \"\n"
        '                "WHERE id = :id")\n'
    )
    compliant_tree = ast.parse(compliant_source)

    compliant_violations = (
        IndeterminateHumanChecks.check_indeterminate_requires_human_mechanism(
            compliant_tree
        )
    )

    assert compliant_violations == []


from unittest.mock import patch


# ID: e293dbbd-081f-44a3-9da5-e4b75a5adb1c
def test_IndeterminateHumanChecks_check_indeterminate_requires_human_mechanism() -> (
    None
):
    sql = (
        "UPDATE core.blackboard_entries "
        "SET status = 'indeterminate', resolution_mechanism = 'reaudit' "
        "WHERE id = :id"
    )
    source = f"import sqlalchemy\ntext({sql!r})\n"
    tree = ast.parse(source)

    check = IndeterminateHumanChecks()
    with (
        patch.object(
            IndeterminateHumanChecks,
            "_resolve_call_name",
            return_value="text",
            create=True,
        ),
        patch.object(
            IndeterminateHumanChecks,
            "_extract_first_string_literal",
            return_value=sql,
            create=True,
        ),
    ):
        violations = check.check_indeterminate_requires_human_mechanism(tree)

    assert isinstance(violations, list)
    assert len(violations) == 1
    assert "indeterminate" in violations[0]
    assert "resolution_mechanism" in violations[0]
