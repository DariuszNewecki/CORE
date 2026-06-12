# src/mind/logic/engines/ast_gate/checks/indeterminate_human_checks.py

"""
ADR-091 D2 Amendment (2026-06-12) — SQL-text scanner for the delegation guard.

The load-bearing invariant (the symmetric twin of the reaudit guard in
``awaiting_reaudit_checks.py``): every UPDATE on core.blackboard_entries that
transitions a row to status='indeterminate' MUST co-assign
``resolution_mechanism = 'human'`` in the same SET clause. A finding marked
indeterminate is, by ADR-091 D2's closing-authority taxonomy, closed by a
human governor — never by ADR-045's reaudit sensor. A site that flips a row to
indeterminate while leaving ``resolution_mechanism = 'reaudit'`` (its birth
value) produces a finding that masquerades in the reaudit queue forever: the
sensor re-detects and re-emits it every cycle, and the F-19 convergence metric
counts it as open work that no sensor can ever clear. That is the #628 defect.

Why this guard differs from the reaudit guard's literal-only match
--------------------------------------------------------------------
``awaiting_reaudit`` is always written as a string literal, so its guard
matches ``SET status = 'awaiting_reaudit'`` directly. ``indeterminate`` is
written two ways: literally (``BlackboardService.mark_indeterminate``) AND via
a bound parameter (``SET status = :status`` in ``update_entry_status`` and the
direct-SQL ``_mark_findings`` paths, where :status may be 'indeterminate'). A
literal-only match would miss the parameterised sites — exactly the live bug
paths. So this check fires on any blackboard_entries UPDATE whose SET body
*references* 'indeterminate' (a literal status assignment, or its inclusion in
a status-terminalising CASE) and requires the SET body to carry a
``resolution_mechanism = … 'human'`` assignment. The detection is scoped to the
SET body (up to WHERE), so a statement that merely *filters* on
``status = 'indeterminate'`` in its WHERE clause is not flagged.
"""

from __future__ import annotations

import ast
import re


# Matches `UPDATE ... blackboard_entries ... SET <setbody>` and captures the
# SET body up to (but not including) the WHERE clause, via the same tempered
# `(?:(?!\bWHERE\b).)*` construction the reaudit guard uses. Scoping to the SET
# body is what keeps WHERE-clause `status = 'indeterminate'` filters (e.g.
# resolve_indeterminate_entry) from being mistaken for a transition.
_BB_UPDATE_SETBODY_RE = re.compile(
    r"(?is)UPDATE\s+(?:core\.)?blackboard_entries\b.*?\bSET\b(?P<setbody>(?:(?!\bWHERE\b).)*)"
)

# The SET body terminalises a row to 'indeterminate' — either a direct literal
# assignment (`status = 'indeterminate'`) or membership in a status CASE.
_INDETERMINATE_TOKEN_RE = re.compile(r"(?i)'indeterminate'")

# The required co-assignment: resolution_mechanism set to (or resolving to)
# 'human'. Tolerant of both the literal form (`resolution_mechanism = 'human'`)
# and the CASE form (`resolution_mechanism = CASE WHEN … THEN 'human' …`).
_HUMAN_MECHANISM_RE = re.compile(r"(?is)\bresolution_mechanism\s*=.*?'human'")


# ID: 1f6309c1-7ab6-4bce-9a8f-66ef0fdecae2
class IndeterminateHumanChecks:
    """ADR-091 D2 Amendment delegation-guard SQL invariant.

    Stateless. The single check method walks an AST tree, finds every
    sqlalchemy.text(...) call, extracts string-literal arguments, and flags
    any blackboard_entries UPDATE whose SET body transitions a row to
    'indeterminate' without co-assigning resolution_mechanism='human'.
    """

    @staticmethod
    # ID: 81c790ad-c413-44fc-bfd1-6c08529a2560
    def check_indeterminate_requires_human_mechanism(tree: ast.AST) -> list[str]:
        """Return one violation message per non-conforming SQL literal.

        Detection targets sqlalchemy.text(...) calls — the only idiomatic
        SQL-literal construction site in this codebase. f-strings and
        concatenation are out of scope for the same reason the reaudit guard
        documents: dynamic SQL construction here is rare and would also bypass
        standard injection hygiene, flagged independently.
        """
        violations: list[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if _resolve_call_name(node.func) != "text":
                continue
            sql_literal = _extract_first_string_literal(node)
            if sql_literal is None:
                continue
            for match in _BB_UPDATE_SETBODY_RE.finditer(sql_literal):
                setbody = match.group("setbody")
                if not _INDETERMINATE_TOKEN_RE.search(setbody):
                    continue
                if _HUMAN_MECHANISM_RE.search(setbody):
                    continue
                line = getattr(node, "lineno", "?")
                violations.append(
                    f"Line {line}: SQL UPDATE transitions core.blackboard_entries "
                    f"to status='indeterminate' without co-assigning "
                    f"`resolution_mechanism = 'human'`. A finding marked "
                    f"indeterminate is closed by a human governor, not by the "
                    f"reaudit sensor; leaving resolution_mechanism='reaudit' "
                    f"makes it masquerade in the reaudit queue forever (#628). "
                    f"Add `resolution_mechanism = 'human'` (literal) or "
                    f"`resolution_mechanism = CASE WHEN :status = 'indeterminate' "
                    f"THEN 'human' ELSE resolution_mechanism END` (parameterised) "
                    f"to the SET clause. See ADR-091 §D2 Amendment (D2-A1/A2)."
                )
        return violations


def _resolve_call_name(func: ast.expr) -> str | None:
    """Return the rightmost name of an ast.Call's func expression.

    Handles both ``text(...)`` (ast.Name) and ``sqlalchemy.text(...)``
    (ast.Attribute) forms; returns None for any other shape.
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
    quoted multi-line literals appear as a single ast.Constant str value.
    f-strings (ast.JoinedStr) and concatenation return None — out of scope.
    """
    if not call.args:
        return None
    first = call.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value
    return None
