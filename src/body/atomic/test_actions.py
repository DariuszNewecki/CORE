# src/body/atomic/test_actions.py

"""
Atomic-action wrapper for the pytest runner.

Wraps shared.infrastructure.validation.test_runner.run_tests with the
register_action + atomic_action decoration pair so the test.execute
capability has decoration backing per ADR-079 D9. When reached via
ActionExecutor.execute("test.execute"), _executor_token is set to
"test.execute" before run_tests runs — chokepoint identity propagates
correctly. The underlying run_tests stays in shared/infrastructure
(pure pytest+persistence infrastructure with no body imports).
"""

from __future__ import annotations

from typing import Any

from body.atomic.registry import ActionCategory, register_action
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.infrastructure.validation.test_runner import run_tests


@register_action(
    action_id="test.execute",
    description="Run the pytest test suite and persist results as Constitutional Evidence",
    category=ActionCategory.CHECK,
    policies=["atomic_actions"],
    requires_db=True,
    requires_vectors=False,
)
@atomic_action(
    action_id="test.execute",
    intent="Execute pytest and persist results to var/reports/ and core.action_results",
    impact=ActionImpact.WRITE_DATA,
    policies=["atomic_actions"],
)
# ID: df9bc040-b62c-47f0-958b-08d42c86152f
async def action_test_execute(**kwargs: Any) -> ActionResult:
    """Dispatch entry-point for the test.execute capability.

    Delegates to run_tests; the executor has already set _executor_token
    to "test.execute" so any FS writes the runner performs authorize
    against test.execute's fs_profile, not the enclosing caller's.
    """
    return await run_tests()
