from __future__ import annotations

import ast

from mind.logic.engines.ast_gate.checks.awaiting_reaudit_checks import (
    AwaitingReauditChecks,
)


# ID: 59241f55-15d9-4300-8a26-6ef7c28941b2
def test_AwaitingReauditChecks_check_reaudit_requires_mechanism() -> None:
    sql = "UPDATE blackboard_entries SET status = 'awaiting_reaudit' WHERE id = :id"
    source = f"result = text({sql!r})\n"
    tree = ast.parse(source)

    violations = AwaitingReauditChecks.check_reaudit_requires_mechanism(tree)

    assert isinstance(violations, list)
    assert len(violations) == 1
    assert "awaiting_reaudit" in violations[0]
    assert "resolution_mechanism = 'reaudit'" in violations[0]
