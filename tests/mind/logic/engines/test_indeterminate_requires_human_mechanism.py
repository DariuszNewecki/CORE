"""Unit tests for the ADR-091 D2 Amendment delegation-guard SQL invariant.

Tests ``IndeterminateHumanChecks.check_indeterminate_requires_human_mechanism``
directly (a pure function over an ``ast.AST`` tree) and via the
``ASTGateEngine.verify`` dispatcher to confirm wiring.

The rule statement (#628): every UPDATE on core.blackboard_entries whose SET
clause transitions a row to status='indeterminate' MUST co-assign
``resolution_mechanism = 'human'`` in the same SET clause. A finding marked
indeterminate is closed by a human governor, never by ADR-045's reaudit
sensor; leaving the birth value 'reaudit' parks it in the reaudit queue
forever.

This guard is the symmetric twin of ``test_reaudit_requires_mechanism`` but
differs in one structural way: indeterminate is written both as a literal
(``mark_indeterminate``) AND via a bound ``:status`` parameter
(``update_entry_status`` and the direct-SQL ``_mark_findings`` paths). The
detection therefore fires on any SET body that references 'indeterminate' —
literal assignment or status-terminalising CASE — and is scoped to the SET
body so WHERE-clause filters on status='indeterminate' are not mistaken for
transitions.
"""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path

import pytest

from mind.logic.engines.ast_gate.checks.indeterminate_human_checks import (
    IndeterminateHumanChecks,
)
from mind.logic.engines.ast_gate.engine import ASTGateEngine
from shared.path_resolver import PathResolver


_CHECK_TYPE = "indeterminate_requires_human_mechanism"


def _check(source: str) -> list[str]:
    """Parse *source* and run the AST check against it directly."""
    tree = ast.parse(textwrap.dedent(source))
    return IndeterminateHumanChecks.check_indeterminate_requires_human_mechanism(tree)


def test_compliant_literal_with_human_emits_no_violation() -> None:
    """The mark_indeterminate shape — literal status='indeterminate' with
    resolution_mechanism='human' co-assigned in the same SET. Zero violations."""
    violations = _check(
        """
        from sqlalchemy import text

        async def mark():
            await session.execute(
                text(
                    \"\"\"
                    UPDATE core.blackboard_entries
                    SET status = 'indeterminate',
                        resolution_mechanism = 'human',
                        resolved_at = now(),
                        updated_at = now()
                    WHERE id = cast(:entry_id as uuid)
                      AND status = 'claimed'
                    \"\"\"
                )
            )
        """
    )
    assert violations == []


def test_compliant_parameterised_case_form_emits_no_violation() -> None:
    """The update_entry_status shape — :status param with the
    resolution_mechanism CASE that resolves to 'human' on indeterminate."""
    violations = _check(
        """
        from sqlalchemy import text

        async def update_status():
            await session.execute(
                text(
                    \"\"\"
                    UPDATE core.blackboard_entries
                    SET status = :status,
                        resolution_mechanism = CASE
                            WHEN :status = 'indeterminate' THEN 'human'
                            ELSE resolution_mechanism
                        END,
                        resolved_at = CASE
                            WHEN :status IN ('resolved', 'abandoned', 'indeterminate')
                                THEN now()
                            ELSE resolved_at
                        END,
                        updated_at = now()
                    WHERE id = :id
                    \"\"\"
                )
            )
        """
    )
    assert violations == []


def test_literal_missing_human_emits_one_violation() -> None:
    """status='indeterminate' set without the human co-assignment → one
    finding citing ADR-091 §D2 Amendment and #628."""
    violations = _check(
        """
        from sqlalchemy import text

        async def broken_mark():
            await session.execute(
                text(
                    \"\"\"
                    UPDATE core.blackboard_entries
                    SET status = 'indeterminate',
                        resolved_at = now(),
                        updated_at = now()
                    WHERE id = :id
                    \"\"\"
                )
            )
        """
    )
    assert len(violations) == 1
    msg = violations[0]
    assert "indeterminate" in msg
    assert "resolution_mechanism" in msg
    assert "ADR-091" in msg


def test_parameterised_missing_human_is_caught() -> None:
    """The subtle case: a :status UPDATE that lists 'indeterminate' only in
    its resolved_at CASE (so it CAN terminalise to indeterminate) but omits
    the resolution_mechanism clause. Must be flagged — this is exactly the
    pre-fix update_entry_status / _mark_findings shape."""
    violations = _check(
        """
        from sqlalchemy import text

        async def broken_update():
            await session.execute(
                text(
                    \"\"\"
                    UPDATE core.blackboard_entries
                    SET status = :status,
                        resolved_at = CASE
                            WHEN :status IN ('resolved', 'abandoned', 'indeterminate')
                                THEN now()
                            ELSE resolved_at
                        END,
                        updated_at = now()
                    WHERE id = :id
                    \"\"\"
                )
            )
        """
    )
    assert len(violations) == 1


def test_where_clause_filter_on_indeterminate_is_ignored() -> None:
    """A statement that merely FILTERS on status='indeterminate' in its WHERE
    (e.g. resolve_indeterminate_entry) while SETting a different status is not
    a transition INTO indeterminate and must not be flagged. Detection is
    scoped to the SET body."""
    violations = _check(
        """
        from sqlalchemy import text

        async def resolve_indeterminate():
            await session.execute(
                text(
                    \"\"\"
                    UPDATE core.blackboard_entries
                    SET status = 'resolved',
                        resolved_at = now()
                    WHERE id = :id
                      AND status = 'indeterminate'
                    \"\"\"
                )
            )
        """
    )
    assert violations == []


def test_non_indeterminate_sql_is_ignored() -> None:
    """SQL touching blackboard_entries but never SETting indeterminate
    (resolve, abandon, status read) is out of scope."""
    violations = _check(
        """
        from sqlalchemy import text

        async def resolve():
            await session.execute(
                text(
                    \"\"\"
                    UPDATE core.blackboard_entries
                    SET status = 'abandoned', resolved_at = now()
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
    """Bare `blackboard_entries` (no schema qualifier) is recognised, mirroring
    the `(?:core\\.)?` allowance in the reaudit guard."""
    violations = _check(
        """
        from sqlalchemy import text

        async def bare():
            await session.execute(
                text(
                    \"\"\"
                    UPDATE blackboard_entries
                    SET status = 'indeterminate'
                    WHERE id = :id
                    \"\"\"
                )
            )
        """
    )
    assert len(violations) == 1


def test_attribute_call_form_text_is_matched() -> None:
    """sqlalchemy.text(...) attribute form resolves the same as bare text()."""
    violations = _check(
        """
        import sqlalchemy

        async def attr_form():
            await session.execute(
                sqlalchemy.text(
                    \"\"\"
                    UPDATE core.blackboard_entries
                    SET status = 'indeterminate'
                    WHERE id = :id
                    \"\"\"
                )
            )
        """
    )
    assert len(violations) == 1


def test_dynamic_sql_via_fstring_is_out_of_scope() -> None:
    """f-string-constructed SQL is not traced — the structural guard targets
    string-literal SQL only, identical scope to the reaudit guard."""
    violations = _check(
        """
        from sqlalchemy import text

        async def dynamic():
            status = "indeterminate"
            await session.execute(
                text(f"UPDATE core.blackboard_entries SET status = '{status}' WHERE id = :id")
            )
        """
    )
    assert violations == []


@pytest.mark.asyncio
async def test_engine_dispatch_for_indeterminate_check_type(tmp_path: Path) -> None:
    """The check is reachable via ASTGateEngine.verify(check_type=...)."""
    file_path = tmp_path / "broken.py"
    file_path.write_text(
        textwrap.dedent(
            """
            from sqlalchemy import text

            async def broken_mark():
                await session.execute(
                    text(
                        \"\"\"
                        UPDATE core.blackboard_entries
                        SET status = 'indeterminate'
                        WHERE id = :id
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


@pytest.mark.parametrize(
    "fixed_file",
    [
        "src/body/services/blackboard_service/blackboard_service.py",
        "src/body/workers/call_site_rewriter.py",
        "src/body/workers/prompt_artifact_writer.py",
    ],
)
def test_shipped_fix_sites_are_compliant(fixed_file: str) -> None:
    """Regression anchor: the four UPDATE sites fixed in this change-set
    (mark_indeterminate lives in blackboard_service.py with update_entry_status)
    must carry the human co-assignment and emit zero violations."""
    source = Path(fixed_file).read_text(encoding="utf-8")
    assert _check(source) == []
