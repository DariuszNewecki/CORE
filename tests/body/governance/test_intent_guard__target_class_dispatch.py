"""Regression tests for ADR-097 step 2 target-class dispatch on check_transaction.

Pins three behaviors that the step 4 dispatch flip will rely on:

1. **Backwards compatibility**: callers that do NOT pass ``target_classes`` see
   byte-identical behavior to pre-ADR-097 callers — hard invariant on
   ``.intent/`` writes, policy rules evaluated, capability tier advisory log.

2. **ephemeral-scratch short-circuit**: when ``target_classes`` maps a path
   to ``"ephemeral-scratch"``, that path skips both the hard invariant and
   policy rule evaluation. This is the structural sanctuary that lets
   shadow_materializer / sandbox writes pass the chokepoint without per-file
   excludes. The capability tier still runs (ADR-079 stage 1 log).

3. **Other classes preserve current behavior**: ``repo-source``,
   ``runtime-output``, and ``governed-artifact`` all hit the same hard
   invariant + policy rule flow today. The differentiated tier semantics for
   ``governed-artifact`` (META validation, API authorization) ship in
   ADR-097 step 6.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from body.governance.intent_guard import IntentGuard
from mind.governance.policy_rule import PolicyRule


def _rule_constitution_block_all_py() -> PolicyRule:
    """A constitution-authority rule that always blocks any *.py path.

    Used to verify the dispatch: when a path lands in repo-source /
    runtime-output / governed-artifact, this rule fires and the
    transaction is invalid. When the same path lands in
    ephemeral-scratch, the rule is bypassed and the transaction
    succeeds.
    """
    return PolicyRule(
        name="test.adr097.always_block",
        pattern="**/*.py",
        action="deny",
        description="Test rule: blocks any .py path",
        severity="blocking",
        source_policy="test_policy_adr097",
        engine=None,
        params={},
        authority="constitution",
    )


def _bare_guard(rules: list[PolicyRule], repo_path: Path) -> IntentGuard:
    """Construct an IntentGuard without invoking __init__.

    Mirrors the pattern in test_intent_guard__audit_engines._bare_guard
    and test_intent_guard__capability_tier_advisory._bare_guard.
    """
    guard = IntentGuard.__new__(IntentGuard)
    guard.repo_path = repo_path
    guard.intent_root = repo_path / ".intent"
    guard.rules = rules
    guard.strict_mode = False
    guard._capabilities = None
    return guard


@pytest.fixture
def guard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> IntentGuard:
    """Guard with one always-blocking constitution rule + projection short-circuit.

    The vocabulary projection check is bypassed (every test's tmp_path
    repo has no .intent/META/vocabulary.json so the real call would
    short-circuit to DEGRADED before dispatch). Capability tier
    advisory runs but with no capabilities loaded, so its log is benign.
    """
    monkeypatch.setattr(
        "body.governance.intent_guard.load_vocabulary_projection",
        lambda _repo_path: {},
    )
    return _bare_guard([_rule_constitution_block_all_py()], repo_path=tmp_path)


# ---------------------------------------------------------------------------
# Backwards compatibility — target_classes=None preserves existing behavior
# ---------------------------------------------------------------------------


def test_backcompat_no_target_classes_blocks_on_constitutional_rule(
    guard: IntentGuard,
) -> None:
    """Pre-ADR-097 callers (no target_classes kwarg) see the constitution
    rule fire and the transaction is invalid. Confirms no behavior
    change for the legacy call path."""
    result = guard.check_transaction(proposed_paths=["src/foo.py"])
    assert result.is_valid is False
    assert any(v.rule_name == "test.adr097.always_block" for v in result.violations)


def test_backcompat_intent_path_hits_hard_invariant(guard: IntentGuard) -> None:
    """Pre-ADR-097 callers writing to .intent/ get the hard invariant block."""
    result = guard.check_transaction(proposed_paths=[".intent/foo.yaml"])
    assert result.is_valid is False
    assert any(
        v.message.startswith("Writes to .intent/") or "intent" in v.message.lower()
        for v in result.violations
    )


# ---------------------------------------------------------------------------
# ephemeral-scratch short-circuit (the load-bearing new behavior)
# ---------------------------------------------------------------------------


def test_ephemeral_scratch_skips_constitutional_rule(guard: IntentGuard) -> None:
    """ADR-097 step 2: ephemeral-scratch class skips policy rule evaluation.
    The transaction succeeds even with an always-blocking rule loaded."""
    result = guard.check_transaction(
        proposed_paths=["var/tmp/sandbox_xxx/foo.py"],
        target_classes={"var/tmp/sandbox_xxx/foo.py": "ephemeral-scratch"},
    )
    assert result.is_valid is True, (
        f"ephemeral-scratch path should bypass policy rules; got violations: "
        f"{result.violations}"
    )
    assert result.violations == []


def test_ephemeral_scratch_skips_substring_bug_target(guard: IntentGuard) -> None:
    """A var/tmp/.../src/foo.py path under ephemeral-scratch classification
    bypasses the rule. This is the bug fix shadow_materializer needs:
    crate content written under var/tmp/<uuid>/src/... no longer trips
    the rule that fires on any *.py path."""
    path = "var/tmp/core-shadow-uuid/shadow/src/body/executor.py"
    result = guard.check_transaction(
        proposed_paths=[path],
        target_classes={path: "ephemeral-scratch"},
    )
    assert result.is_valid is True
    assert result.violations == []


def test_ephemeral_scratch_skips_even_intent_path(guard: IntentGuard) -> None:
    """Verifies the dispatch ordering: ephemeral-scratch is evaluated
    BEFORE the hard invariant. A pathologically-classified .intent/
    path would skip the hard invariant — caller responsibility, not
    a guard bug. This pins the ordering, not the policy."""
    result = guard.check_transaction(
        proposed_paths=[".intent/scratch.yaml"],
        target_classes={".intent/scratch.yaml": "ephemeral-scratch"},
    )
    assert result.is_valid is True
    assert result.violations == []


# ---------------------------------------------------------------------------
# Other classes preserve current behavior
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "target_class",
    ["repo-source", "runtime-output", "governed-artifact"],
)
def test_non_ephemeral_classes_still_hit_rules(
    guard: IntentGuard, target_class: str
) -> None:
    """All non-ephemeral classes go through the existing hard-invariant
    + policy-rule path. Today this means identical behavior to the
    no-target_classes case; ADR-097 step 6 differentiates
    governed-artifact (API-mediated tier)."""
    result = guard.check_transaction(
        proposed_paths=["src/foo.py"],
        target_classes={"src/foo.py": target_class},
    )
    assert result.is_valid is False, (
        f"target_class={target_class} should NOT skip rule evaluation; "
        f"only ephemeral-scratch does (today)."
    )
    assert any(v.rule_name == "test.adr097.always_block" for v in result.violations)


def test_unknown_target_class_falls_through_to_default_behavior(
    guard: IntentGuard,
) -> None:
    """An unrecognized target_class value (e.g., a future class not yet
    handled) defers to current behavior (no shortcut taken). Pins
    fail-safe semantics: future classes default to strict evaluation,
    not loose."""
    result = guard.check_transaction(
        proposed_paths=["src/foo.py"],
        target_classes={"src/foo.py": "future-undefined-class"},
    )
    assert result.is_valid is False
    assert any(v.rule_name == "test.adr097.always_block" for v in result.violations)


# ---------------------------------------------------------------------------
# Mixed transactions
# ---------------------------------------------------------------------------


def test_mixed_transaction_respects_per_path_class(guard: IntentGuard) -> None:
    """A transaction with both ephemeral-scratch and repo-source paths
    blocks ONLY on the repo-source path. Per-path dispatch isn't
    transaction-wide."""
    result = guard.check_transaction(
        proposed_paths=["var/tmp/scratch.py", "src/real.py"],
        target_classes={
            "var/tmp/scratch.py": "ephemeral-scratch",
            "src/real.py": "repo-source",
        },
    )
    assert result.is_valid is False
    # The blocking violation comes from src/real.py, not var/tmp/scratch.py.
    blocking_paths = {
        v.path for v in result.violations if v.rule_name == "test.adr097.always_block"
    }
    assert "src/real.py" in blocking_paths
    assert "var/tmp/scratch.py" not in blocking_paths
