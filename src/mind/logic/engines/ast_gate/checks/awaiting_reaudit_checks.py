# src/mind/logic/engines/ast_gate/checks/awaiting_reaudit_checks.py

"""
ADR-091 D2 Revision B — SQL-text scanner for the reaudit guard invariant.

The load-bearing invariant: every UPDATE on core.blackboard_entries that
transitions a row to status='awaiting_reaudit' MUST co-occur with
`resolution_mechanism = 'reaudit'` in the same WHERE clause. A SQL site
that flips a row to awaiting_reaudit without the resolution_mechanism guard
would park a self_resolve or human finding into ADR-045's sensor re-audit
queue, where no audit sensor can adjudicate it because none owns the subject
prefix's truth claim.

The check walks ast.Call nodes for sqlalchemy.text(...) invocations,
extracts string-literal arguments, regex-matches the awaiting_reaudit
transition pattern in each, and flags any literal containing the
transition without the guard predicate. The runtime guard ships in
src/body/services/blackboard_service/blackboard_proposal_service.py
(revive_findings_for_failed_proposal) and is the only conforming site
at engine-landing.
"""

from __future__ import annotations

import ast
import re


# Matches `UPDATE ... blackboard_entries ... SET ... status = 'awaiting_reaudit'`.
# Case-insensitive (SQL is conventionally case-insensitive even when the
# codebase mixes cases), whitespace/newline-tolerant via re.DOTALL, schema-
# qualified or bare. The `.*?` between table and SET allows any column list
# or quoted aliases between them; the tempered `(?:(?!\bWHERE\b).)*?` between
# SET and the status assignment allows additional SET assignments (status
# doesn't have to be the first SET column) without crossing into the WHERE
# clause — drainer UPDATEs legitimately filter on `status = 'awaiting_reaudit'`
# in WHERE while SETting status to a different terminal value, and must not
# trigger this rule.
_AWAITING_REAUDIT_TRANSITION_RE = re.compile(
    r"(?is)UPDATE\s+(?:core\.)?blackboard_entries\b.*?\bSET\b(?:(?!\bWHERE\b).)*?\bstatus\s*=\s*'awaiting_reaudit'"
)

# Matches the guard predicate anywhere in the SQL literal. Whitespace-tolerant.
# Doesn't care about position within WHERE — any order of predicates passes.
_GUARD_PREDICATE_RE = re.compile(r"(?i)\bresolution_mechanism\s*=\s*'reaudit'")


# ID: 4f9c7e1a-2b8d-4536-9f0c-8a5e3b1d7c92
class AwaitingReauditChecks:
    """ADR-091 D2 reaudit-guard SQL invariant.

    Stateless. The single check method walks an AST tree, finds every
    sqlalchemy.text(...) call (the codebase's idiomatic SQL-literal
    construction), extracts string-literal arguments, and flags any
    awaiting_reaudit UPDATE missing the resolution_mechanism guard.
    """

    @staticmethod
    # ID: 7a2d9b4e-6f1c-4583-bd09-3c8e5a2b1f74
    def check_reaudit_requires_mechanism(tree: ast.AST) -> list[str]:
        """Return one violation message per non-conforming SQL literal.

        Detection is targeted at sqlalchemy.text(...) calls — the only
        idiomatic SQL-literal construction site in this codebase. Both
        bare ``text("...")`` and attribute ``sqlalchemy.text("...")``
        forms are matched. f-strings (ast.JoinedStr) and concatenation
        are not traced; the rule statement scopes to string-literal SQL
        because dynamic SQL construction in this codebase is rare and
        out-of-scope for the structural guard. If a future site assembles
        the UPDATE dynamically and bypasses this check, that site would
        also bypass standard SQL-injection hygiene and should be flagged
        independently.
        """
        violations: list[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func_name = _resolve_call_name(node.func)
            if func_name != "text":
                continue
            sql_literal = _extract_first_string_literal(node)
            if sql_literal is None:
                continue
            if not _AWAITING_REAUDIT_TRANSITION_RE.search(sql_literal):
                continue
            if _GUARD_PREDICATE_RE.search(sql_literal):
                continue
            line = getattr(node, "lineno", "?")
            violations.append(
                f"Line {line}: SQL UPDATE transitions to "
                f"status='awaiting_reaudit' without the ADR-091 D2 reaudit "
                f"guard. Add `AND resolution_mechanism = 'reaudit'` to the "
                f"WHERE clause; the invariant is that only findings whose "
                f"emitter declared resolution_mechanism='reaudit' may be "
                f"parked into awaiting_reaudit by ADR-045's sensor "
                f"re-audit machinery. See ADR-091 §Revision B (b)."
            )
        return violations


def _resolve_call_name(func: ast.expr) -> str | None:
    """Return the rightmost name of an ast.Call's func expression.

    Handles both ``text(...)`` (ast.Name) and ``sqlalchemy.text(...)``
    (ast.Attribute) forms. Returns None for any other shape (e.g., a
    callable returned by another call), since those are too rare in this
    codebase to warrant tracing.
    """
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _extract_first_string_literal(call: ast.Call) -> str | None:
    """Return the value of the first string-literal positional argument, or
    None if no positional arg is present or the first arg is not a literal.

    sqlalchemy.text() takes the SQL string as the first positional. Triple-
    quoted multi-line literals appear as ast.Constant with str value already
    joined; no separate handling needed. f-strings (ast.JoinedStr) and
    concatenation expressions return None — those are out of scope per the
    rule statement.
    """
    if not call.args:
        return None
    first = call.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value
    return None
