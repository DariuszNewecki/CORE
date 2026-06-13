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
    policies=["rules/code/purity"],
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


@register_action(
    action_id="test.sandbox_validate",
    description="Execute a single generated test file in isolation; reject if it fails to collect or run",
    category=ActionCategory.CHECK,
    policies=["rules/code/purity"],
    requires_db=True,
    requires_vectors=False,
)
@atomic_action(
    action_id="test.sandbox_validate",
    intent="Run a freshly-generated test file via pytest and fail the build_tests flow if it does not pass",
    impact=ActionImpact.WRITE_DATA,
    policies=["atomic_actions"],
)
# ID: c966c90d-43ec-47fa-8cc5-41c22f74383d
async def action_test_sandbox_validate(
    *,
    source_file: str | None = None,
    test_file: str | None = None,
    **kwargs: Any,
) -> ActionResult:
    """Step-1 "is it working" gate for a generated test (#574 dynamic follow-on).

    Code generation is two steps — a working .py, then a CORE-compliant .py. The
    static gate (IntentGuard import-resolution + #589 shape checks) and the fix.*
    auto-heal cover compliance; this covers *working*: it executes the generated
    test file so one that imports cleanly and looks right but fails at runtime —
    wrong assertion, signature drift, broken fixture — is caught. Wired as the
    required final step of flow.build_tests: a non-zero pytest exit halts the flow
    (FlowExecutor required-step semantics) so the failing test never reaches the
    autonomous commit.

    Takes ``source_file`` (the flow-routed parameter) and derives the test path via
    the governed source->test mapping — identical to how build.tests resolves it,
    so both act on the same single path. ``test_file`` may be passed directly to
    override (direct invocation / tests).
    """
    if not test_file and source_file:
        from shared.infrastructure.intent.test_coverage_paths import (
            source_to_test_path,
        )

        test_file = source_to_test_path(source_file)
    if not test_file:
        return ActionResult(
            action_id="test.sandbox_validate",
            ok=False,
            data={
                "error": "test.sandbox_validate requires 'source_file' or 'test_file'"
            },
            impact=ActionImpact.WRITE_DATA,
        )
    result = await run_tests(target=test_file, action_id="test.sandbox_validate")
    if not result.ok:
        result.data["violations"] = [
            {
                "file": test_file,
                "rule": "test.generated.must_execute",
                "message": (
                    "Generated test failed sandbox execution: "
                    + str(result.data.get("summary", "unknown failure"))
                ),
            }
        ]
    return result
