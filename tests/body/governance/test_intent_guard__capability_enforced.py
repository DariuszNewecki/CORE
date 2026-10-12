# tests/body/governance/test_intent_guard__capability_enforced.py
"""ADR-079 stage 2, writer by writer: enforced capabilities are denied for real.

A capability in ENFORCED_CAPABILITIES that writes outside its fs_profile makes
check_transaction invalid (the write is blocked). The same out-of-profile write
by a capability not yet enforced, or a write with no capability, stays
advisory: logged, not blocked.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from body.governance.intent_guard import (
    CAPABILITY_RULE_ID,
    ENFORCED_CAPABILITIES,
    IntentGuard,
)
from shared.infrastructure.intent.operational_capabilities import (
    FsPatternEntry,
    OperationalCapability,
)


def _capability(cap_id: str) -> OperationalCapability:
    modify = (FsPatternEntry(path_pattern="src/**/*.py", modes=("dev", "live")),)
    return OperationalCapability(
        id=cap_id,
        description="test fixture",
        risk="safe",
        fs_profile=(("read", ()), ("create", ()), ("modify", modify), ("delete", ())),
    )


@pytest.fixture
def guard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> IntentGuard:
    monkeypatch.setattr(
        "body.governance.intent_guard.load_vocabulary_projection", lambda _r: {}
    )
    guard = IntentGuard.__new__(IntentGuard)
    guard.repo_path = tmp_path
    guard.intent_root = tmp_path / ".intent"
    guard.rules = []
    guard.strict_mode = False
    guard._capabilities = {
        "fix.format": _capability("fix.format"),
        "fix.docstrings": _capability("fix.docstrings"),
    }
    return guard


def _check(guard: IntentGuard, path: str, capability: str | None, op: str = "modify"):
    return guard.check_transaction(
        proposed_paths=[path],
        op_classes={path: op},
        calling_capability=capability,
        current_mode="live",
    )


def test_fix_format_is_enforced() -> None:
    assert "fix.format" in ENFORCED_CAPABILITIES
    assert "fix.docstrings" not in ENFORCED_CAPABILITIES


def test_enforced_capability_outside_its_profile_is_denied(guard: IntentGuard) -> None:
    result = _check(guard, "docs/readme.md", "fix.format")
    assert result.is_valid is False
    [violation] = [v for v in result.violations if v.rule_name == CAPABILITY_RULE_ID]
    assert "path_not_authorized" in violation.message


def test_enforced_capability_with_an_undeclared_operation_is_denied(
    guard: IntentGuard,
) -> None:
    result = _check(guard, "src/x.py", "fix.format", op="delete")
    assert result.is_valid is False


def test_enforced_capability_inside_its_profile_is_allowed(guard: IntentGuard) -> None:
    result = _check(guard, "src/body/x.py", "fix.format")
    assert result.is_valid is True
    assert not result.violations


def test_capability_not_yet_enforced_stays_advisory(guard: IntentGuard) -> None:
    result = _check(guard, "docs/readme.md", "fix.docstrings")
    assert result.is_valid is True


def test_a_write_with_no_capability_stays_advisory(guard: IntentGuard) -> None:
    result = _check(guard, "docs/readme.md", None)
    assert result.is_valid is True
