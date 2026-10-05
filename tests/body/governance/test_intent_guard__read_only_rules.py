# tests/body/governance/test_intent_guard__read_only_rules.py
"""#936: the three .intent read-only rules are enforced by IntentGuard tier 1.

governance.constitution.read_only, architecture.constitution_read_only and
architecture.meta_read_only were mapped to glob_gate over src/**/*.py with
.intent/** prohibited -- disjoint scopes, so the audit could never fire. The
real protection is IntentGuard's hard invariant on every write that reaches
FileHandler. These are the G2 fixtures for the passive_gate (class A) mapping:
a real refusal for each protected tree, and an ordinary src/ write allowed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from body.governance.intent_guard import IntentGuard
from shared.infrastructure.intent.target_class import resolve_target_class


_READ_ONLY_RULE_ID = "governance.constitution.read_only"


@pytest.fixture
def guard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> IntentGuard:
    monkeypatch.setattr(
        "body.governance.intent_guard.load_vocabulary_projection",
        lambda _repo_path: {},
    )
    guard = IntentGuard.__new__(IntentGuard)
    guard.repo_path = tmp_path
    guard.intent_root = tmp_path / ".intent"
    guard.rules = []
    guard.strict_mode = False
    guard._capabilities = None
    return guard


def _classes(path: str) -> dict[str, str]:
    # The classification FileHandler supplies for the same path.
    return {path: resolve_target_class(path)}


def _assert_refused(guard: IntentGuard, path: str) -> None:
    classes = _classes(path)
    assert classes[path] != "ephemeral-scratch"

    result = guard.check_transaction(proposed_paths=[path], target_classes=classes)

    assert result.is_valid is False
    assert [v.rule_name for v in result.violations] == [_READ_ONLY_RULE_ID]
    assert result.violations[0].source_policy == "constitution"


def test_write_under_intent_is_refused(guard: IntentGuard) -> None:
    """governance.constitution.read_only: any path under .intent/."""
    _assert_refused(guard, ".intent/rules/architecture/core_safety.json")


def test_write_under_intent_constitution_is_refused(guard: IntentGuard) -> None:
    """architecture.constitution_read_only: .intent/constitution/."""
    _assert_refused(guard, ".intent/constitution/CORE-CONSTITUTION.md")


def test_write_under_intent_meta_is_refused(guard: IntentGuard) -> None:
    """architecture.meta_read_only: .intent/META/."""
    _assert_refused(guard, ".intent/META/enums.json")


def test_ordinary_src_write_is_allowed(guard: IntentGuard) -> None:
    path = "src/body/services/example.py"

    result = guard.check_transaction(
        proposed_paths=[path], target_classes=_classes(path)
    )

    assert result.is_valid is True
    assert result.violations == []
