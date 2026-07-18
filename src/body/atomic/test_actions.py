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

import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

from body.atomic.registry import ActionCategory, register_action
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.infrastructure.validation.test_runner import run_tests
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)


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
    core_context: CoreContext | None = None,
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

    ADR-106: when this runs as a step of a *sandboxed* flow, ``core_context`` is
    the scoped context whose ``git_service.repo_path`` is the hermetic worktree —
    where the freshly-generated test actually lives. We thread that path to
    ``run_tests`` so pytest executes inside the worktree, not the main tree
    (which does not yet have the generated file). Unsandboxed / direct callers
    leave ``core_context`` None and fall back to the global ``settings.REPO_PATH``.
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
    repo_root = None
    if core_context is not None and core_context.git_service is not None:
        repo_root = core_context.git_service.repo_path
    result = await run_tests(
        target=test_file, action_id="test.sandbox_validate", repo_root=repo_root
    )
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


@register_action(
    action_id="test.candidate_validate",
    description="Validate a not-yet-accepted candidate test snippet against pytest in ephemeral scratch",
    category=ActionCategory.CHECK,
    policies=["rules/code/purity"],
    requires_db=True,
    requires_vectors=False,
)
@atomic_action(
    action_id="test.candidate_validate",
    intent="Materialize a candidate test file under var/tmp/ ephemeral scratch and run pytest against it, so the generation acceptance loop never writes to the real target test path",
    impact=ActionImpact.WRITE_DATA,
    policies=["atomic_actions"],
)
# ID: 5f8a2c94-6b1e-4d37-9a80-2c5e7f9b3d16
async def action_test_candidate_validate(
    *,
    source_file: str,
    target_path: str,
    candidate_content: str,
    core_context: CoreContext | None = None,
    **kwargs: Any,
) -> ActionResult:
    """Evaluate one generation candidate without ever touching production paths (#815).

    PytestAcceptanceCondition previously wrote `base_content + candidate` straight
    to the real `target_path` on every iteration (rejected candidates included) via
    `CoreContext.file_service`. When that context wasn't scoped to a sandbox
    worktree, candidates leaked into the main repo tree; even scoped, it collided
    with `build.test_for_symbol`'s own later append of the same accepted snippet
    (a duplicate-definition bug). Neither problem can occur here: this action
    writes only to a fresh `var/tmp/candidate_validate/<token>/` directory
    (`FileHandler.write` classifies `var/tmp/` as ephemeral-scratch — no
    syntax/schema gates, no ID-anchor injection), runs pytest against that scratch
    copy, and removes the directory before returning. Nothing under `tests/` or
    `src/` is ever written by this action; `target_path` is used only to name the
    scratch file, never as a write destination.

    `source_file` is not consulted for path derivation — `target_path` is already
    resolved by the caller (mirrors test.sandbox_validate's contract, which is
    invoked identically once a candidate is accepted) — it is threaded through only
    for traceability in the returned data.
    """
    if core_context is None or core_context.file_handler is None:
        return ActionResult(
            action_id="test.candidate_validate",
            ok=False,
            data={"error": "core_context with file_handler is required"},
            impact=ActionImpact.WRITE_DATA,
        )

    scratch_dir = f"var/tmp/candidate_validate/{uuid.uuid4().hex}"
    scratch_rel_path = f"{scratch_dir}/{Path(target_path).name}"

    try:
        core_context.file_handler.write(scratch_rel_path, candidate_content)
    except Exception as exc:
        return ActionResult(
            action_id="test.candidate_validate",
            ok=False,
            data={
                "error": f"candidate scratch write failed: {exc}",
                "source_file": source_file,
                "target_path": target_path,
            },
            impact=ActionImpact.WRITE_DATA,
        )

    repo_root = core_context.git_service.repo_path if core_context.git_service else None
    try:
        result = await run_tests(
            target=scratch_rel_path,
            action_id="test.candidate_validate",
            repo_root=repo_root,
        )
    finally:
        try:
            core_context.file_handler.remove_tree(scratch_dir)
        except Exception as exc:
            logger.warning(
                "test.candidate_validate: scratch cleanup failed for %s: %s",
                scratch_dir,
                exc,
            )

    result.data["source_file"] = source_file
    result.data["target_path"] = target_path
    if not result.ok:
        result.data["violations"] = [
            {
                "file": target_path,
                "rule": "test.candidate.must_execute",
                "message": (
                    "Candidate test failed sandboxed execution: "
                    + str(result.data.get("summary", "unknown failure"))
                ),
            }
        ]
    return result
