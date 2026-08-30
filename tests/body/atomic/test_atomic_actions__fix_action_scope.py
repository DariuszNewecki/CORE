# tests/body/atomic/test_atomic_actions__fix_action_scope.py
"""Real regression proof for atomic_actions.fix_action_scope (#842).

Rule: "The atomic action 'fix.imports' is exclusively scoped to import
ordering and sorting... MUST NOT be interpreted as validating import
correctness or module existence. A separate 'check.imports' action is
the designated authority for import resolution verification."

This was previously mapped `advisory` / "enforced by code review and
convention" -- inadequate for a rule labelled blocking. The separation is
in fact a structural property of the ruff `--select` rule-code sets each
action builds: `fix.imports` selects only `I` (import sorting) and never
resolves `--fix` to anything else; `check.imports` selects only
`F821,F401` (resolution/staleness) and never passes `--fix`. These tests
assert the actual command each action builds, not the docstring's claim,
and would fail if either action's scope drifted into the other's.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from body.atomic.check_actions import action_check_imports
from body.atomic.fix import action_fix_imports
from shared.governance_token import authorize_execution


def _select_arg(cmd: list[str]) -> str:
    return cmd[cmd.index("--select") + 1]


async def test_fix_imports_select_is_sorting_only_dry_run() -> None:
    with patch("shared.utils.subprocess_utils.run_poetry_command") as mock_run:
        with authorize_execution("fix.imports"):
            result = await action_fix_imports(write=False)
    assert result.ok
    cmd = mock_run.call_args[0][1]
    assert _select_arg(cmd) == "I"
    assert "--fix" not in cmd


async def test_fix_imports_select_is_sorting_only_write() -> None:
    with patch("shared.utils.subprocess_utils.run_poetry_command") as mock_run:
        with authorize_execution("fix.imports"):
            result = await action_fix_imports(write=True)
    assert result.ok
    cmd = mock_run.call_args[0][1]
    assert _select_arg(cmd) == "I"
    assert "--fix" in cmd  # the only thing write=True changes


async def test_fix_imports_never_selects_resolution_codes() -> None:
    """fix.imports must never gain F821/F401 in --select -- that would
    cross into check.imports' resolution-verification authority."""
    with patch("shared.utils.subprocess_utils.run_poetry_command") as mock_run:
        with authorize_execution("fix.imports"):
            await action_fix_imports(write=True)
    select = _select_arg(mock_run.call_args[0][1])
    assert "F821" not in select
    assert "F401" not in select


async def test_check_imports_select_is_resolution_verification_only() -> None:
    fake_result = MagicMock(stdout="[]", returncode=0)
    with patch(
        "body.atomic.check_actions.subprocess.run", return_value=fake_result
    ) as mock_run:
        with authorize_execution("check.imports"):
            result = await action_check_imports(write=False)
    assert result.ok
    cmd = mock_run.call_args[0][0]
    assert _select_arg(cmd) == "F821,F401"
    assert "--fix" not in cmd
    assert "I" not in _select_arg(cmd).split(",")


async def test_check_imports_never_mutates_regardless_of_write_flag() -> None:
    """check.imports is ActionImpact.READ_ONLY -- write=True must not
    introduce --fix or otherwise change the command's mutating shape."""
    fake_result = MagicMock(stdout="[]", returncode=0)
    with patch(
        "body.atomic.check_actions.subprocess.run", return_value=fake_result
    ) as mock_run:
        with authorize_execution("check.imports"):
            await action_check_imports(write=True)
    cmd = mock_run.call_args[0][0]
    assert "--fix" not in cmd
    assert _select_arg(cmd) == "F821,F401"


async def test_fix_imports_and_check_imports_select_sets_are_disjoint() -> None:
    """Structural proof of atomic_actions.fix_action_scope: the two
    actions' ruff --select rule-code sets never overlap."""
    with patch("shared.utils.subprocess_utils.run_poetry_command") as mock_fix:
        with authorize_execution("fix.imports"):
            await action_fix_imports(write=True)
    fix_select = set(_select_arg(mock_fix.call_args[0][1]).split(","))

    fake_result = MagicMock(stdout="[]", returncode=0)
    with patch(
        "body.atomic.check_actions.subprocess.run", return_value=fake_result
    ) as mock_check:
        with authorize_execution("check.imports"):
            await action_check_imports(write=False)
    check_select = set(_select_arg(mock_check.call_args[0][0]).split(","))

    assert fix_select.isdisjoint(check_select)
