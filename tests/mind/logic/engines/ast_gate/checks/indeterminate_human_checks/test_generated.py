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
