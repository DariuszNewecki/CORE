"""Regression tests pinning ``_AUDIT_ENGINES`` in ``body.governance.intent_guard``.

Closes the audit trail for #142 (resolved by commit ``efd18421``) and the
duplicate stale-backlog observation #292. Both issues' symptom — 128
``fix.placeholders`` proposals failing with the verbatim statement of
``cli.resource_first`` ("CLI commands MUST follow 'resource action [flags]'
pattern (depth=2)…") — re-opens the moment any passive-marker engine is
removed from the skip set, because the underlying rule is enforced at
audit time by the ``cli_gate`` engine (also driven from
``core-admin admin self-check``), not at ``FileHandler``-mediated writes.

Also closes #823: three DB-audited governance rules
(``governance.commit_authorship_integrity``,
``governance.proposal_finalization_integrity``,
``governance.consequence_evidence_degraded`` — detected post-hoc by
``CommitAuthorshipAuditWorker`` against database rows, never at write time)
declare ``engine: passive_gate`` *directly*, not via one of
``PASSIVE_ALIASES``. The alias list was never meant to also carry the alias
*target*, so the literal ``"passive_gate"`` name fell through this skip
unexempted, hard-blocking every ``src/**/*.py`` create or modify —
including ``fix.ids``'s real ``write=True`` path — under the three rules'
``authority: constitution``. This is a rule-applicability/phase
classification defect: these rules correctly remain constitutional-severity
for their real job (auditing persisted proposal/consequence evidence
post-hoc); they simply must never participate in an in-flight file-write
decision. The fix widens ``_AUDIT_ENGINES`` by the literal engine name, not
by touching the rules' ``authority`` or ``enforcement`` fields.

The original #142 fix did not include a regression test. These tests are
that defense: a parametrised set-membership check that fails loudly if the
skip set is shrunk, plus a behavioural check that ``_check_against_rules``
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

# Cross-artifact engines whose checks need the whole YAML against
# all-of-src/ substrate (e.g., ADR-079 D9 phantom-decoration). They have no
# per-file write-time check; evaluating them in check_against_rules
# produces false-positive blocks whose message is the rule statement.
CROSS_ARTIFACT_ENGINES = [
    "taxonomy_gate",
]

# Context-level-only engines (ADR-076): every check_type walks the live
# whole-system substrate (Typer app, system state, data contracts, runtime
# graph) and the per-file ``verify()`` explicitly rejects per-file dispatch as
# a mapping error. Absent from the skip set, a write to any matching path
# surfaces their rules — and for constitutional-authority ``cli_gate`` rules,
# hard-blocks it. This is #659: every ``src/cli/**`` write blocked, the
# ConstitutionalViolationError rendering ``quality.type_safety`` (the first
# surfaced violation) as a misleading "MyPy" cause. Same class as #142, which
# added the ``runtime_check`` alias but never ``cli_gate`` itself.
CONTEXT_LEVEL_ENGINES = [
    "cli_gate",
    "workflow_gate",
    "contracts_gate",
    "runtime_gate",
]

# The literal passive_gate engine name — the alias *target*, declared
# directly by mappings whose detector is a worker auditing persisted
# database state post-hoc (not one of PASSIVE_ALIASES, which are names that
# *resolve to* passive_gate). #823.
PASSIVE_GATE_LITERAL_ENGINE = [
    "passive_gate",
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


@pytest.mark.parametrize("engine", CROSS_ARTIFACT_ENGINES)
def test_cross_artifact_engine_remains_in_audit_set(engine: str) -> None:
    """Cross-artifact engines (whole-YAML against all-of-src/ checks) must
    stay in ``_AUDIT_ENGINES`` so write-time evaluation skips them.

    For ADR-079 D9's ``taxonomy_gate``: removing it would make every
    FileHandler write evaluate the operational-capabilities backing check,
    surfacing every YAML cap_id without a per-write decoration match as a
    bogus block — the rule's statement as the block reason — even though
    the check has no per-file semantics.
    """
    assert engine in _AUDIT_ENGINES, (
        f"{engine!r} was removed from _AUDIT_ENGINES — cross-artifact "
        f"engines have no per-file write-time check; evaluating them here "
        f"produces false positives whose message is the rule statement."
    )


# ---- Skip behaviour: _check_against_rules honours the set ----------------


@pytest.mark.parametrize("engine", CONTEXT_LEVEL_ENGINES)
def test_context_level_engine_remains_in_audit_set(engine: str) -> None:
    """Context-level-only engines must stay in ``_AUDIT_ENGINES``.

    Removing any re-opens #659: a constitutional ``cli_gate`` rule
    (``cli.resource_first`` et al.) hard-blocks every ``src/cli/**`` write,
    with the ConstitutionalViolationError rendering ``quality.type_safety``
    (the first surfaced violation) as a misleading "MyPy" block reason. These
    engines declare themselves context-level and their per-file ``verify()``
    rejects per-file dispatch — they have no write-time check.
    """
    assert engine in _AUDIT_ENGINES, (
        f"{engine!r} was removed from _AUDIT_ENGINES — this re-opens the #659 "
        f"regression (constitutional cli_gate rules hard-blocking src/cli/** "
        f"writes). See src/body/governance/intent_guard.py."
    )


@pytest.mark.parametrize("engine", PASSIVE_GATE_LITERAL_ENGINE)
def test_passive_gate_literal_engine_remains_in_audit_set(engine: str) -> None:
    """The literal ``passive_gate`` engine name must stay in ``_AUDIT_ENGINES``.

    Removing it re-opens #823: governance.commit_authorship_integrity,
    governance.proposal_finalization_integrity, and
    governance.consequence_evidence_degraded — each ``authority:
    constitution``, each declaring ``engine: passive_gate`` directly, each
    scoped ``src/**/*.py`` — hard-block every file create/modify, including
    fix.ids's real write=True path, with no in-flight file content able to
    satisfy a check that can only ever be evaluated against database rows.
    """
    assert engine in _AUDIT_ENGINES, (
        f"{engine!r} was removed from _AUDIT_ENGINES — this re-opens #823: "
        f"every src/**/*.py write (including fix.ids's real write=True path) "
        f"hard-blocks under the three passive_gate-engine constitutional "
        f"governance rules. See src/body/governance/intent_guard.py."
    )


@pytest.mark.parametrize(
    "engine",
    PASSIVE_MARKER_ENGINES
    + CONTENT_ANALYSIS_ENGINES
    + CROSS_ARTIFACT_ENGINES
    + CONTEXT_LEVEL_ENGINES
    + PASSIVE_GATE_LITERAL_ENGINE,
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


# ---- #823: reproduce the exact original failure with the real, loaded rules ----


def test_check_transaction_permits_any_src_py_write_against_real_rules(
    tmp_path: Path,
) -> None:
    """Direct reproduction of #823 using a fully-initialized IntentGuard.

    Before the fix: any src/**/*.py create or modify was blocked by
    ``governance.commit_authorship_integrity``,
    ``governance.proposal_finalization_integrity``, and
    ``governance.consequence_evidence_degraded`` — the three
    ``authority: constitution``, ``engine: passive_gate`` rules loaded from
    the repo's real ``.intent/`` — because ``passive_gate`` (the literal
    engine name, not one of its aliases) was absent from ``_AUDIT_ENGINES``.

    This does not need a database, an ActionExecutor, or a CoreContext:
    ``check_transaction`` is a pure rule/path evaluation over the real,
    repo-loaded rule set, which is exactly what blocked the write in
    production — reproducing it here needs nothing more.
    """
    repo_root = Path(__file__).resolve().parents[3]
    guard = IntentGuard(repo_root)

    result = guard.check_transaction(
        ["src/body/analyzers/_does_not_need_to_exist.py"],
        op_classes={"src/body/analyzers/_does_not_need_to_exist.py": "create"},
        target_classes={
            "src/body/analyzers/_does_not_need_to_exist.py": "repo-source"
        },
    )

    constitutional_rule_names = {
        v.rule_name
        for v in result.violations
        if v.severity == "constitutional"
    }
    assert constitutional_rule_names == set(), (
        "check_transaction hard-blocked a plain src/**/*.py write via "
        f"{constitutional_rule_names} — #823 has regressed. These rules are "
        "detected post-hoc by CommitAuthorshipAuditWorker against database "
        "rows; they must never surface at write time."
    )
    assert result.is_valid is True
