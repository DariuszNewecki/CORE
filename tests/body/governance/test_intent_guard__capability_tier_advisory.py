"""Stage-1 advisory capability-tier evaluation tests (ADR-079 D5).

Pins all six D5 branches (3-8) for ``_evaluate_capability_tier_advisory``
plus the fail-soft no-op cases. Each test asserts:

  1. The ``chokepoint.advisory.would-deny`` log marker fires (or doesn't,
     for permit/no-op).
  2. The reason code in the log matches the D5 branch.
  3. The tier does NOT mutate ``violations`` or ``is_valid`` — stage 1 is
     log-only per ADR-079 D10 stage 1.

The tests bypass ``IntentGuard.__init__`` (which loads the live ``.intent/``
repo) and inject hand-built ``OperationalCapability`` fixtures, matching
the pattern in ``test_intent_guard__audit_engines.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from body.governance.intent_guard import IntentGuard
from shared.infrastructure.intent.operational_capabilities import (
    FsPatternEntry,
    OperationalCapability,
)


_ADVISORY_MARKER = "chokepoint.advisory.would-deny"
_PERMIT_MARKER = "chokepoint.advisory.would-permit"


def _make_capability(
    cap_id: str = "fix.format",
    *,
    modify_patterns: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("src/**/*.py", ("dev", "live")),
    ),
    create_patterns: tuple[tuple[str, tuple[str, ...]], ...] = (),
    delete_patterns: tuple[tuple[str, tuple[str, ...]], ...] = (),
    read_patterns: tuple[tuple[str, tuple[str, ...]], ...] = (),
) -> OperationalCapability:
    """Build a frozen OperationalCapability with a configurable fs_profile.

    The four op-class keys (modify/create/delete/read) match the
    enums.json fs_operation_class enum order; the loader enforces this
    invariant — we mirror it here so the as_mapping view yields the keys
    the chokepoint tier expects.
    """

    def _entries(spec: tuple[tuple[str, tuple[str, ...]], ...]) -> tuple[FsPatternEntry, ...]:
        return tuple(FsPatternEntry(path_pattern=p, modes=m) for p, m in spec)

    fs_profile = (
        ("read", _entries(read_patterns)),
        ("create", _entries(create_patterns)),
        ("modify", _entries(modify_patterns)),
        ("delete", _entries(delete_patterns)),
    )
    return OperationalCapability(
        id=cap_id,
        description="test fixture",
        risk="safe",
        fs_profile=fs_profile,
    )


def _bare_guard(
    capabilities: dict[str, OperationalCapability] | None,
) -> IntentGuard:
    """Construct an IntentGuard without invoking __init__.

    Mirrors ``test_intent_guard__audit_engines._bare_guard``: we only
    exercise ``_evaluate_capability_tier_advisory``, so policy loading
    and projection-DEGRADED machinery are irrelevant.
    """
    guard = IntentGuard.__new__(IntentGuard)
    guard.repo_path = Path("/tmp")
    guard.intent_root = Path("/tmp/.intent")
    guard.rules = []
    guard.strict_mode = False
    guard._capabilities = capabilities
    return guard


@pytest.fixture
def caplog_intent(caplog: pytest.LogCaptureFixture) -> pytest.LogCaptureFixture:
    """Capture INFO+ from the IntentGuard logger only."""
    caplog.set_level("DEBUG", logger="body.governance.intent_guard")
    return caplog


# ---------------------------------------------------------------------------
# D5 branch coverage
# ---------------------------------------------------------------------------


def test_branch_3_no_capability_context_logs_advisory(
    caplog_intent: pytest.LogCaptureFixture,
) -> None:
    """Capability=None with taxonomy loaded → no_capability_context advisory."""
    guard = _bare_guard({"fix.format": _make_capability()})
    guard._evaluate_capability_tier_advisory(
        path_str="src/foo.py",
        op_class="modify",
        capability=None,
        mode="dev",
    )
    msgs = [r.getMessage() for r in caplog_intent.records]
    assert any(_ADVISORY_MARKER in m and "no_capability_context" in m for m in msgs)


def test_branch_4_unknown_capability_logs_advisory(
    caplog_intent: pytest.LogCaptureFixture,
) -> None:
    """Capability not in taxonomy → unknown_capability advisory."""
    guard = _bare_guard({"fix.format": _make_capability()})
    guard._evaluate_capability_tier_advisory(
        path_str="src/foo.py",
        op_class="modify",
        capability="phantom.action",
        mode="dev",
    )
    msgs = [r.getMessage() for r in caplog_intent.records]
    assert any(_ADVISORY_MARKER in m and "unknown_capability" in m for m in msgs)


def test_branch_5_operation_not_authorized_logs_advisory(
    caplog_intent: pytest.LogCaptureFixture,
) -> None:
    """Capability's fs_profile has empty list for this op_class → operation_not_authorized."""
    cap = _make_capability(
        cap_id="check.foo",
        modify_patterns=(),
        create_patterns=(),
        delete_patterns=(),
    )
    guard = _bare_guard({"check.foo": cap})
    guard._evaluate_capability_tier_advisory(
        path_str="src/foo.py",
        op_class="modify",
        capability="check.foo",
        mode="dev",
    )
    msgs = [r.getMessage() for r in caplog_intent.records]
    assert any(_ADVISORY_MARKER in m and "operation_not_authorized" in m for m in msgs)


def test_branch_6_path_not_authorized_logs_advisory(
    caplog_intent: pytest.LogCaptureFixture,
) -> None:
    """Pattern list non-empty but no match → path_not_authorized with declared list."""
    cap = _make_capability(
        modify_patterns=(("src/specific/**/*.py", ("dev", "live")),),
    )
    guard = _bare_guard({"fix.format": cap})
    guard._evaluate_capability_tier_advisory(
        path_str="src/elsewhere/foo.py",
        op_class="modify",
        capability="fix.format",
        mode="dev",
    )
    msgs = [r.getMessage() for r in caplog_intent.records]
    assert any(
        _ADVISORY_MARKER in m
        and "path_not_authorized" in m
        and "src/specific/**/*.py" in m
        for m in msgs
    )


def test_branch_7_mode_not_authorized_logs_advisory(
    caplog_intent: pytest.LogCaptureFixture,
) -> None:
    """Pattern matches but the entry's modes exclude current mode → mode_not_authorized."""
    cap = _make_capability(
        modify_patterns=(("src/**/*.py", ("live",)),),
    )
    guard = _bare_guard({"fix.format": cap})
    guard._evaluate_capability_tier_advisory(
        path_str="src/foo.py",
        op_class="modify",
        capability="fix.format",
        mode="dev",
    )
    msgs = [r.getMessage() for r in caplog_intent.records]
    assert any(_ADVISORY_MARKER in m and "mode_not_authorized" in m for m in msgs)


def test_branch_8_permit_emits_no_would_deny(
    caplog_intent: pytest.LogCaptureFixture,
) -> None:
    """Matching pattern + mode → permit; would-deny marker absent, would-permit at DEBUG."""
    cap = _make_capability(
        modify_patterns=(("src/**/*.py", ("dev", "live")),),
    )
    guard = _bare_guard({"fix.format": cap})
    guard._evaluate_capability_tier_advisory(
        path_str="src/foo.py",
        op_class="modify",
        capability="fix.format",
        mode="dev",
    )
    msgs = [r.getMessage() for r in caplog_intent.records]
    assert not any(_ADVISORY_MARKER in m for m in msgs)
    assert any(_PERMIT_MARKER in m for m in msgs)


# ---------------------------------------------------------------------------
# Fail-soft no-op cases (stage 1 must never crash on missing inputs)
# ---------------------------------------------------------------------------


def test_no_op_when_capabilities_failed_to_load(
    caplog_intent: pytest.LogCaptureFixture,
) -> None:
    """If __init__ couldn't load the taxonomy, tier silently no-ops."""
    guard = _bare_guard(None)
    guard._evaluate_capability_tier_advisory(
        path_str="src/foo.py",
        op_class="modify",
        capability="fix.format",
        mode="dev",
    )
    msgs = [r.getMessage() for r in caplog_intent.records]
    assert not any(_ADVISORY_MARKER in m for m in msgs)
    assert not any(_PERMIT_MARKER in m for m in msgs)


def test_no_op_when_op_class_missing(
    caplog_intent: pytest.LogCaptureFixture,
) -> None:
    """Callers without op-class context (e.g. validate_generated_code path probe) skip the tier."""
    guard = _bare_guard({"fix.format": _make_capability()})
    guard._evaluate_capability_tier_advisory(
        path_str="src/foo.py",
        op_class=None,
        capability="fix.format",
        mode="dev",
    )
    assert not any(
        _ADVISORY_MARKER in r.getMessage() or _PERMIT_MARKER in r.getMessage()
        for r in caplog_intent.records
    )


def test_no_op_when_mode_missing(
    caplog_intent: pytest.LogCaptureFixture,
) -> None:
    """Same skip when the caller didn't supply mode."""
    guard = _bare_guard({"fix.format": _make_capability()})
    guard._evaluate_capability_tier_advisory(
        path_str="src/foo.py",
        op_class="modify",
        capability="fix.format",
        mode=None,
    )
    assert not any(
        _ADVISORY_MARKER in r.getMessage() or _PERMIT_MARKER in r.getMessage()
        for r in caplog_intent.records
    )


# ---------------------------------------------------------------------------
# Public-surface non-mutation contract
# ---------------------------------------------------------------------------


def test_check_transaction_capability_tier_does_not_mutate_verdict(
    monkeypatch: pytest.MonkeyPatch,
    caplog_intent: pytest.LogCaptureFixture,
) -> None:
    """ADR-079 stage 1 verification §3: the capability tier path through
    ``check_transaction`` must NOT change ``is_valid`` or
    ``violations`` — even when the tier would deny every path.

    Exercises the public surface (not the helper directly) so a future
    regression where ``_evaluate_capability_tier_advisory`` accidentally
    appends to the violations list, or ``check_transaction`` starts
    consulting the tier's verdict in stage 1, fails this test.
    """
    # Bypass the vocabulary-projection DEGRADED pre-check — bare guard's
    # /tmp repo has no .intent/META/vocabulary.json so the real call would
    # short-circuit before the capability tier runs.
    monkeypatch.setattr(
        "body.governance.intent_guard.load_vocabulary_projection",
        lambda _repo_path: {},
    )

    cap = _make_capability(
        cap_id="fix.format",
        modify_patterns=(("src/specific/**/*.py", ("dev", "live")),),
    )
    guard = _bare_guard({"fix.format": cap})

    # Unknown capability → D5 branch 4 (capability tier would deny).
    # Path is under src/ so no tier-1 .intent/ hit; bare guard's empty
    # rules list means no tier-2/3 contributions.
    result = guard.check_transaction(
        proposed_paths=["src/foo.py"],
        op_classes={"src/foo.py": "modify"},
        calling_capability="phantom.unknown",
        current_mode="dev",
    )

    # Premise: the capability tier actually ran (advisory log fired).
    msgs = [r.getMessage() for r in caplog_intent.records]
    assert any(
        _ADVISORY_MARKER in m and "unknown_capability" in m for m in msgs
    ), "Capability tier didn't run — test premise broken; rest of assertions vacuous."

    # Contract: stage 1 is observability-only.
    assert result.is_valid is True, (
        "Stage 1 contract violated: capability tier flipped is_valid."
    )
    assert result.violations == [], (
        "Stage 1 contract violated: capability tier added violations: "
        f"{result.violations}"
    )
