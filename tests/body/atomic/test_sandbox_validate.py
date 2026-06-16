# tests/body/atomic/test_sandbox_validate.py
"""Basic test for the test.sandbox_validate gate (#574 dynamic follow-on).

The action is @atomic_action-governed, so a direct call raises
GovernanceBypassError by design — full behavioral validation (does it execute the
generated test and halt flow.build_tests on failure) is an integration concern,
exercised through ActionExecutor + the flow + pytest. This unit test covers the
guard via the underlying function: a sandbox-validate with no resolvable target
must refuse (ok=False), never silently pass — a missing target reading as success
would defeat the gate.
"""

from __future__ import annotations

import pytest

from body.atomic.test_actions import action_test_sandbox_validate


@pytest.mark.asyncio
async def test_refuses_with_no_target() -> None:
    fn = action_test_sandbox_validate.__wrapped__
    result = await fn(source_file=None, test_file=None)
    assert result.ok is False
    assert "source_file" in result.data["error"]
