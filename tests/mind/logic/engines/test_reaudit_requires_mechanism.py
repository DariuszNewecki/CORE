"""Unit tests for ADR-091 D2 Revision B reaudit-guard SQL invariant check.

Tests the ``AwaitingReauditChecks.check_reaudit_requires_mechanism`` AST
check directly (the check is a pure function over an ``ast.AST`` tree) and
via the ``ASTGateEngine.verify`` dispatcher to confirm wiring.

The rule statement: every UPDATE on core.blackboard_entries that
transitions a row to status='awaiting_reaudit' MUST co-occur with
`resolution_mechanism = 'reaudit'` in the same WHERE clause. The check
walks ast.Call nodes for sqlalchemy.text(...) invocations and flags any
string-literal argument containing the awaiting_reaudit transition
pattern without the guard predicate.

The compliant baseline is the real ``revive_findings_for_failed_proposal``
SQL at ``src/body/services/blackboard_service/blackboard_proposal_service.py``
(commit b2887afe). Tests pin: compliant SQL passes; broken SQL is flagged;
non-awaiting_reaudit SQL is ignored; multi-line literals are parsed; non-
``text()`` calls and dynamic/non-literal SQL are out of scope per the
rule's structural-only stance.
"""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path

import pytest

from mind.logic.engines.ast_gate.checks.awaiting_reaudit_checks import (
    AwaitingReauditChecks,
)
from mind.logic.engines.ast_gate.engine import ASTGateEngine
from shared.path_resolver import PathResolver


_CHECK_TYPE = "reaudit_requires_reaudit_mechanism"


def _check(source: str) -> list[str]:
    """Parse *source* and run the AST check against it directly."""
    tree = ast.parse(textwrap.dedent(source))
    return AwaitingReauditChecks.check_reaudit_requires_mechanism(tree)


def test_compliant_sql_with_guard_emits_no_violation() -> None:
    """The canonical revive_findings_for_failed_proposal shape — both the
    awaiting_reaudit transition AND the resolution_mechanism guard present
    in the same text() literal. Must emit zero violations."""
    violations = _check(
        """
        from sqlalchemy import text

        async def revive():
            await session.execute(
                text(
                    \"\"\"
                    UPDATE core.blackboard_entries
                    SET status = 'awaiting_reaudit',
                        updated_at = now()
                    WHERE entry_type = 'finding'
                      AND resolution_mechanism = 'reaudit'
                      AND status = 'deferred_to_proposal'
                    \"\"\"
                )
            )
        """
    )
    assert violations == []


def test_missing_guard_emits_one_violation() -> None:
    """awaiting_reaudit UPDATE without the resolution_mechanism guard →
    one finding citing ADR-091 §Revision B (b)."""
    violations = _check(
        """
        from sqlalchemy import text

        async def broken_revive():
            await session.execute(
                text(
                    \"\"\"
                    UPDATE core.blackboard_entries
                    SET status = 'awaiting_reaudit',
                        updated_at = now()
                    WHERE entry_type = 'finding'
                      AND status = 'deferred_to_proposal'
                    \"\"\"
                )
            )
        """
    )
    assert len(violations) == 1
    msg = violations[0]
    assert "awaiting_reaudit" in msg
    assert "ADR-091" in msg
    assert "resolution_mechanism" in msg


def test_non_awaiting_reaudit_sql_is_ignored() -> None:
    """SQL touching blackboard_entries but NOT transitioning to
    awaiting_reaudit (resolve, defer, abandon, status read) is out of scope."""
    violations = _check(
        """
        from sqlalchemy import text

        async def resolve():
            await session.execute(
                text(
                    \"\"\"
                    UPDATE core.blackboard_entries
                    SET status = 'resolved', resolved_at = now()
                    WHERE id = :entry_id
                    \"\"\"
                )
            )
            await session.execute(
                text("SELECT * FROM core.blackboard_entries WHERE status = 'open'")
            )
        """
    )
    assert violations == []


def test_bare_schema_table_form_is_matched() -> None:
    """Schema-qualified `core.blackboard_entries` and bare `blackboard_entries`
    must both be recognized — the regex uses `(?:core\\.)?` precisely so
    drift to the bare form (which would still hit the same table) is caught."""
    violations = _check(
        """
        from sqlalchemy import text

        async def bare_form():
            await session.execute(
                text(
                    \"\"\"
                    UPDATE blackboard_entries
                    SET status = 'awaiting_reaudit'
                    WHERE id = :entry_id
                    \"\"\"
                )
            )
        """
    )
    assert len(violations) == 1


def test_attribute_call_form_text_is_matched() -> None:
    """sqlalchemy.text(...) attribute-access form should resolve the same as
    bare text(...) — the rule shouldn't depend on import style."""
    violations = _check(
        """
        import sqlalchemy

        async def attr_form():
            await session.execute(
                sqlalchemy.text(
                    \"\"\"
                    UPDATE core.blackboard_entries
                    SET status = 'awaiting_reaudit'
                    WHERE id = :entry_id
                    \"\"\"
                )
            )
        """
    )
    assert len(violations) == 1


def test_non_text_call_with_sql_string_is_ignored() -> None:
    """A function call that happens to take a SQL-looking string but is
    NOT sqlalchemy.text() is out of scope. The rule scopes to text()
    because that's the canonical SQL-literal entry point in this codebase
    — other call shapes are too rare to grant credit either way."""
    violations = _check(
        """
        async def doc_string_only():
            log("UPDATE core.blackboard_entries SET status = 'awaiting_reaudit'")
        """
    )
    assert violations == []


def test_dynamic_sql_via_fstring_is_out_of_scope() -> None:
    """f-string-constructed SQL is not traced — the rule's structural guard
    targets string-literal SQL only. This is the deliberate scope of the
    rule statement, and dynamic SQL construction at the awaiting_reaudit
    transition would also bypass standard SQL hygiene and should be
    flagged by a separate rule. No violation here."""
    violations = _check(
        """
        from sqlalchemy import text

        async def dynamic():
            status = "awaiting_reaudit"
            await session.execute(
                text(f"UPDATE core.blackboard_entries SET status = '{status}' WHERE id = :id")
            )
        """
    )
    # f-string is ast.JoinedStr, not ast.Constant — the check skips it.
    assert violations == []


@pytest.mark.asyncio
async def test_engine_dispatch_for_reaudit_check_type(tmp_path: Path) -> None:
    """The check is reachable via ASTGateEngine.verify(check_type=...)."""
    file_path = tmp_path / "broken.py"
    file_path.write_text(
        textwrap.dedent(
            """
            from sqlalchemy import text

            async def broken_revive():
                await session.execute(
                    text(
                        \"\"\"
                        UPDATE core.blackboard_entries
                        SET status = 'awaiting_reaudit'
                        WHERE id = :entry_id
                        \"\"\"
                    )
                )
            """
        ),
        encoding="utf-8",
    )
    engine = ASTGateEngine(path_resolver=PathResolver(repo_root=tmp_path))
    result = await engine.verify(file_path, {"check_type": _CHECK_TYPE})
    assert result.ok is False
    assert len(result.violations) == 1


def test_two_violations_in_same_file_are_each_reported() -> None:
    """If a file has two broken UPDATE sites, both are reported. The check
    walks ast.Call nodes; one finding per non-conforming text() literal."""
    violations = _check(
        """
        from sqlalchemy import text

        async def two_broken():
            await session.execute(
                text("UPDATE core.blackboard_entries SET status = 'awaiting_reaudit'")
            )
            await session.execute(
                text("UPDATE core.blackboard_entries SET status = 'awaiting_reaudit', updated_at = now() WHERE status = 'deferred_to_proposal'")
            )
        """
    )
    assert len(violations) == 2
