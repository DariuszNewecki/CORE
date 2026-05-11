"""Regression tests pinning ``_AUDIT_ENGINES`` in ``body.governance.intent_guard``.

Closes the audit trail for #142 (resolved by commit ``efd18421``) and the
duplicate stale-backlog observation #292. Both issues' symptom — 128
``fix.placeholders`` proposals failing with the verbatim statement of
``cli.resource_first`` ("CLI commands MUST follow 'resource action [flags]'
pattern (depth=2)…") — re-opens the moment any passive-marker engine is
removed from the skip set, because the underlying rule is enforced at
``core-admin admin self-check`` time (``audit_cli_registry()``), not at
``FileHandler``-mediated writes.

The original fix did not include a regression test. These tests are that
defense: a parametrised set-membership check that fails loudly if the skip
set is shrunk, plus a behavioural check that ``_check_against_rules``
honours the skip, plus a negative control that pins the skip to engine
identity rather than to "any rule".
"""

from __future__ import annotations

from pathlib import Path

import pytest

from body.governance.intent_guard import _AUDIT_ENGINES, IntentGuard
from mind.governance.policy_rule import PolicyRule


PASSIVE_MARKER_ENGINES = [
    "runtime_check",
    "python_runtime",
    "dataclass_validation",
    "type_system",
    "advisory",
    "runtime_metric",
]

CONTENT_ANALYSIS_ENGINES = [
    "ast_gate",
    "glob_gate",
    "knowledge_gate",
    "llm_gate",
    "regex_gate",
]


def _bare_guard(rules: list[PolicyRule]) -> IntentGuard:
    """Construct an ``IntentGuard`` instance without invoking ``__init__``.

    ``IntentGuard.__init__`` loads policies from ``.intent/`` and resolves
    executable rules against the running repo — irrelevant for these tests,
    which only exercise ``_check_against_rules`` against hand-built
    ``PolicyRule`` fixtures. Bypassing ``__init__`` keeps the unit test
    deterministic and independent of repo state.
    """
    guard = IntentGuard.__new__(IntentGuard)
    guard.repo_path = Path("/tmp")
    guard.intent_root = Path("/tmp/.intent")
    guard.rules = rules
    guard.strict_mode = False
    return guard


def _rule_with_engine(engine: str | None) -> PolicyRule:
    """Build a constitution-authority rule that matches every ``.py`` under ``src/``."""
    return PolicyRule(
        name=f"test.rule.{engine or 'none'}",
        pattern="src/**/*.py",
        action="deny",
        description=f"test rule with engine={engine}",
        severity="blocking",
        source_policy=f"test_policy_{engine or 'none'}",
        engine=engine,
        params={},
        authority="constitution",
    )


# ---- Set-membership: the skip set itself --------------------------------


@pytest.mark.parametrize("engine", PASSIVE_MARKER_ENGINES)
def test_passive_marker_engine_remains_in_audit_set(engine: str) -> None:
    """Passive-marker engines must stay in ``_AUDIT_ENGINES``.

    Removing any of these re-opens the fix.placeholders → cli.resource_first
    false-block path that produced 128 historical failures (#142, #292).
    """
    assert engine in _AUDIT_ENGINES, (
        f"{engine!r} was removed from _AUDIT_ENGINES — this re-enables the "
        f"#142/#292 regression. See src/body/governance/intent_guard.py "
        f"and commit efd18421."
    )


@pytest.mark.parametrize("engine", CONTENT_ANALYSIS_ENGINES)
def test_content_analysis_engine_remains_in_audit_set(engine: str) -> None:
    """Content-analysis engines require file content (audit phase only).

    They have no write-time check; evaluating them at write time produces
    false positives whose block message is the rule's statement.
    """
    assert engine in _AUDIT_ENGINES, (
        f"{engine!r} was removed from _AUDIT_ENGINES — content-analysis "
        f"engines have no write-time check; evaluating them here produces "
        f"false positives."
    )


# ---- Skip behaviour: _check_against_rules honours the set ----------------


@pytest.mark.parametrize(
    "engine", PASSIVE_MARKER_ENGINES + CONTENT_ANALYSIS_ENGINES
)
def test_rule_with_audit_engine_produces_no_write_time_violation(
    engine: str,
) -> None:
    """A rule whose engine is in ``_AUDIT_ENGINES`` must short-circuit in
    ``_check_against_rules`` even when its path pattern matches the target.

    This is the exact behaviour that resolved #142: ``cli.resource_first``
    declares ``engine: runtime_check``; once ``runtime_check`` joined the
    skip set, ``fix.placeholders`` writes to any ``src/**/*.py`` stopped
    surfacing the CLI rule's statement as a block reason.
    """
    guard = _bare_guard([_rule_with_engine(engine)])
    path_str = "src/will/workers/violation_remediator.py"
    abs_path = guard.repo_path / path_str

    violations = guard._check_against_rules(path_str, abs_path)

    assert violations == [], (
        f"Rule with engine={engine!r} produced {len(violations)} violation(s) "
        f"at write time — the skip in _check_against_rules is not honouring "
        f"_AUDIT_ENGINES. The #142/#292 regression is re-opened."
    )


# ---- Negative control: the skip is by engine, not by rule ----------------


def test_rule_with_non_audit_engine_still_produces_violation() -> None:
    """A rule whose engine is NOT in ``_AUDIT_ENGINES`` must still produce a
    violation when its path pattern matches.

    Pins the skip to the engine set identity. If a future refactor made
    ``_check_against_rules`` skip *all* engine-bearing rules (a plausible
    over-correction of #142), this control would fail.
    """
    synthetic_engine = "synthetic_non_audit_engine_for_test"
    assert synthetic_engine not in _AUDIT_ENGINES  # invariant for this test

    guard = _bare_guard([_rule_with_engine(synthetic_engine)])
    path_str = "src/will/workers/violation_remediator.py"
    abs_path = guard.repo_path / path_str

    violations = guard._check_against_rules(path_str, abs_path)

    assert len(violations) == 1
    assert violations[0].rule_name == f"test.rule.{synthetic_engine}"


def test_rule_with_no_engine_still_produces_violation() -> None:
    """A legacy rule with ``engine=None`` must still produce a violation.

    Pins the skip behaviour for the ``None`` case explicitly — ``None in
    frozenset(...)`` is ``False``, so legacy rules without engine dispatch
    continue to fire at write time as they always did.
    """
    guard = _bare_guard([_rule_with_engine(None)])
    path_str = "src/will/workers/violation_remediator.py"
    abs_path = guard.repo_path / path_str

    violations = guard._check_against_rules(path_str, abs_path)

    assert len(violations) == 1
    assert violations[0].rule_name == "test.rule.none"


# ---- Path scoping is still respected -------------------------------------


def test_audit_engine_rule_not_evaluated_when_pattern_does_not_match() -> None:
    """Sanity: the engine-skip path runs after pattern matching. A
    non-matching path produces zero violations regardless of engine.
    """
    guard = _bare_guard([_rule_with_engine("runtime_check")])
    path_str = "docs/architecture.md"
    abs_path = guard.repo_path / path_str

    violations = guard._check_against_rules(path_str, abs_path)

    assert violations == []
