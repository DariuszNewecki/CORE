# tests/body/atomic/test_assisted_actions.py
"""Guard tests for the assisted.validate_diff safety gate (ADR-109 #654).

The action is @atomic_action-governed, so a direct call raises
GovernanceBypassError by design; full behavioral validation (apply the diff in a
hermetic worktree, run audit + ruff + mapped tests, gate approval) is an
integration concern exercised through ActionExecutor. These unit tests cover the
guards via the underlying function (``.__wrapped__``): the gate must REFUSE
(ok=False) on missing inputs — never silently pass, since a missing patch or rule
reading as success would defeat the gate.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from body.atomic.assisted_actions import (
    action_assisted_apply_diff,
    action_assisted_validate_diff,
)


@pytest.mark.asyncio
async def test_refuses_without_patch() -> None:
    fn = action_assisted_validate_diff.__wrapped__
    result = await fn(
        patch=None, finding_rule="purity.no_orphan_files", core_context=MagicMock()
    )
    assert result.ok is False
    assert "patch" in result.data["error"]


@pytest.mark.asyncio
async def test_refuses_without_finding_rule() -> None:
    fn = action_assisted_validate_diff.__wrapped__
    result = await fn(
        patch="--- a/x\n+++ b/x\n", finding_rule=None, core_context=MagicMock()
    )
    assert result.ok is False
    assert "finding_rule" in result.data["error"]


@pytest.mark.asyncio
async def test_refuses_without_git_service() -> None:
    fn = action_assisted_validate_diff.__wrapped__
    ctx = MagicMock()
    ctx.git_service = None
    result = await fn(
        patch="--- a/x\n+++ b/x\n",
        finding_rule="purity.no_orphan_files",
        core_context=ctx,
    )
    assert result.ok is False
    assert "git_service" in result.data["error"]


@pytest.mark.asyncio
async def test_apply_diff_refuses_without_patch() -> None:
    fn = action_assisted_apply_diff.__wrapped__
    result = await fn(patch=None, core_context=MagicMock())
    assert result.ok is False
    assert "patch" in result.data["error"]


@pytest.mark.asyncio
async def test_apply_diff_refuses_without_git_service() -> None:
    fn = action_assisted_apply_diff.__wrapped__
    ctx = MagicMock()
    ctx.git_service = None
    result = await fn(patch="--- a/x\n+++ b/x\n", core_context=ctx)
    assert result.ok is False
    assert "git_service" in result.data["error"]
