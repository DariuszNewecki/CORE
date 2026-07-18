# src/will/agents/acceptance/conditions.py
"""
AcceptanceCondition protocol and concrete implementations (ADR-135 D3).

AcceptanceCondition is the injectable predicate that IterativeCoderAgent and
PromptModelIterativeAgent use to determine whether a generated code string
should be accepted or retried. Each implementation encapsulates one acceptance
strategy; CompositeAcceptanceCondition combines multiple strategies with AND
semantics.

Layer: Will. Implementations that require subprocess MUST NOT use it directly —
they delegate to Body actions via ActionExecutor (architecture.will.must_delegate_to_body).

ADR-140 Amendment 2026-07-14 (later): the protocol's `task: ExecutionTask` parameter
was dropped — unused by all three implementations, and a vestige of the
ExecutionTask-based IterativeCoderAgent design that does not fit
PromptModelIterativeAgent's context-dict + target_path shape. Per-condition
configuration is constructor-injected instead (target_path, source_file, executor,
base_content).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from shared.logger import getLogger
from shared.utils.test_gen_utils import strip_leading_future_imports


logger = getLogger(__name__)


@dataclass
# ID: 3761195a-9a0a-43ce-8c43-aecd21bb3163
class AcceptanceResult:
    """Outcome of evaluating an AcceptanceCondition against generated code."""

    accepted: bool
    violation_summary: str
    """Fed as pain_signal to the next IterativeCoderAgent iteration."""

    violations: list[str] = field(default_factory=list)
    """Detailed list stored in execution_results for diagnostics."""


@runtime_checkable
# ID: c972117d-49b0-4843-b96e-ca8a9f30ddba
class AcceptanceCondition(Protocol):
    """
    Injectable predicate for IterativeCoderAgent (ADR-135 D3).

    Implementations evaluate a generated code string against one acceptance
    criterion and return an AcceptanceResult. The violation_summary is
    threaded back to the LLM as pain_signal on the next iteration.
    """

    # ID: 6aba3694-9c4f-4c40-871c-5831e808fd3a
    async def evaluate(self, code: str) -> AcceptanceResult: ...


# ID: bf652987-cefd-4601-9bb9-37b449ae5447
class IntentGuardAcceptanceCondition:
    """
    AcceptanceCondition backed by IntentGuard AST validation.

    Validates the generated code snippet against the constitutional rules
    that apply to the target path's component_type. Available in-process;
    no I/O, no subprocess.
    """

    def __init__(
        self, repo_root: Path, target_path: str, component_type: str = "test"
    ) -> None:
        self._repo_root = repo_root
        self._target_path = target_path
        self._component_type = component_type

    # ID: c50ca242-0c6f-4a3c-a4f2-a42e8cf5bbd7
    async def evaluate(self, code: str) -> AcceptanceResult:
        from body.governance.intent_guard import get_intent_guard

        intent_guard = get_intent_guard(repo_path=self._repo_root)
        try:
            validation = intent_guard.validate_generated_code(
                code=code,
                pattern_id="test_file",
                component_type=self._component_type,
                target_path=self._target_path,
            )
        except Exception as exc:
            logger.error("IntentGuardAcceptanceCondition: raised: %s", exc)
            return AcceptanceResult(
                accepted=False,
                violation_summary=f"IntentGuard raised: {exc}",
                violations=[str(exc)],
            )

        if validation.is_valid:
            return AcceptanceResult(accepted=True, violation_summary="")

        violations = [
            f"[{getattr(v, 'rule_name', 'unknown')}] {getattr(v, 'message', '')}"
            for v in validation.violations
        ]
        return AcceptanceResult(
            accepted=False,
            violation_summary="\n".join(violations),
            violations=violations,
        )


# ID: 76e1f64e-810c-484c-ba12-d32b54c84337
class PytestAcceptanceCondition:
    """
    AcceptanceCondition that runs the generated test via test.candidate_validate.

    Delegates test execution to Body via ActionExecutor — Will MUST NOT invoke
    subprocess directly (governance.dangerous_execution_primitives). The worktree
    must already be sandboxed (ADR-106) before this condition is used.

    #815: this condition never writes to `target_path` — the real test file's
    location — at all, for any candidate, accepted or rejected. It previously
    wrote `base_content + code` there directly via `file_service` on every
    evaluate() call, which (a) was not scoped to the sandbox worktree even when
    running inside one, so rejected candidates leaked into the main repo tree,
    and (b) once file_service scoping was fixed, would have collided with
    `build.test_for_symbol`'s own later append of the same accepted snippet — a
    duplicate-definition bug. `test.candidate_validate` (Body) materializes each
    candidate under `var/tmp/` ephemeral scratch instead, runs pytest there, and
    cleans up — `target_path` is passed through only so the action can name the
    scratch file and attribute results, never as a write destination. The single
    authoritative writer of `target_path` remains `build.test_for_symbol`, after
    acceptance.
    """

    def __init__(
        self,
        executor: object,
        source_file: str,
        target_path: str,
        base_content: str,
    ) -> None:
        self._executor = executor
        self._source_file = source_file
        self._target_path = target_path
        self._base_content = base_content

    # ID: 1761e499-621c-4daa-9c40-0e124f6b27b2
    async def evaluate(self, code: str) -> AcceptanceResult:
        from shared.protocols.executor import ActionExecutorProtocol

        if not isinstance(self._executor, ActionExecutorProtocol):
            return AcceptanceResult(
                accepted=False,
                violation_summary="PytestAcceptanceCondition: executor not wired",
            )

        snippet_body = strip_leading_future_imports(code)
        if self._base_content:
            full_content = self._base_content.rstrip() + "\n\n\n" + snippet_body + "\n"
        else:
            full_content = (
                "from __future__ import annotations\n\n\n" + snippet_body + "\n"
            )

        try:
            result = await self._executor.execute(
                "test.candidate_validate",
                write=False,
                source_file=self._source_file,
                target_path=self._target_path,
                candidate_content=full_content,
            )
        except Exception as exc:
            logger.error(
                "PytestAcceptanceCondition: test.candidate_validate raised: %s", exc
            )
            return AcceptanceResult(
                accepted=False,
                violation_summary=f"test.candidate_validate raised: {exc}",
                violations=[str(exc)],
            )

        if result.ok:
            return AcceptanceResult(accepted=True, violation_summary="")

        error = (
            result.data.get("error", "pytest validation failed")
            if isinstance(result.data, dict)
            else "pytest validation failed"
        )
        return AcceptanceResult(
            accepted=False,
            violation_summary=error,
            violations=[error],
        )


# ID: 6a4c94d1-b2ec-4faf-85bc-74b47708b23a
class CompositeAcceptanceCondition:
    """
    AND-composition of multiple AcceptanceConditions (ADR-135 D3).

    Evaluates conditions in declaration order. Returns the first failing
    condition's result. All conditions must pass for accepted=True.
    """

    def __init__(self, conditions: list[AcceptanceCondition]) -> None:
        self._conditions = conditions

    # ID: b8314c80-7b68-4e58-9161-b2dfaa784ba8
    async def evaluate(self, code: str) -> AcceptanceResult:
        for condition in self._conditions:
            result = await condition.evaluate(code)
            if not result.accepted:
                return result
        return AcceptanceResult(accepted=True, violation_summary="")
