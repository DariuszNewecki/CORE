# src/body/flows/executor.py
"""
FlowExecutor — the Body-layer dispatcher for constitutional Flows.

Mirrors ActionExecutor in structure and governance contract. Resolves
a flow_id to its FlowDefinition, executes each step in declaration order
via ActionExecutor (for AtomicAction steps) or recursively via
FlowExecutor (for nested Flow steps), and returns a FlowResult.

Constitutional alignment: CORE-Flow.md §6

Key invariants enforced here:
- write=False is propagated to every step without exception.
- A required step failure halts execution immediately.
- An optional step failure is recorded and execution continues.
- FlowExecutor never posts to the Blackboard — that is Worker territory.
- FlowExecutor never creates Proposals — that is Worker territory.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from body.flows.registry import FlowStep, StepKind, flow_registry
from body.flows.result import FlowResult, StepResult
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext


logger = getLogger(__name__)


# ID: ebd9a0de-3e90-4c97-af3a-49847598fda8
class FlowExecutor:
    """
    Universal execution gateway for constitutional Flows.

    Architecture:
    - Resolves flow_id from FlowRegistry
    - Dispatches AtomicAction steps via ActionExecutor
    - Dispatches nested Flow steps recursively via FlowExecutor
    - Propagates write=False to every step unconditionally
    - Halts on required step failure; continues on optional step failure
    - Returns FlowResult — never raises

    Usage:
        executor = FlowExecutor(core_context)
        result = await executor.execute("flow.fix_code", write=True)
    """

    def __init__(self, core_context: CoreContext) -> None:
        self._core_context = core_context
        self._registry = flow_registry

    # ID: 6896dd9d-063b-4c19-86e5-246b28738651
    async def execute(
        self,
        flow_id: str,
        write: bool = False,
        **params: Any,
    ) -> FlowResult:
        """
        Execute a Flow by flow_id.

        Args:
            flow_id: The registered flow_id to execute.
            write:   Dry-run flag. Propagated to every step unchanged.
                     write=False means no step may mutate state.
            **params: Runtime parameters merged with each step's static
                      params. Step static params are overridden by caller
                      params of the same key.

        Returns:
            FlowResult — always. Never raises.
        """
        start = time.time()

        # 1. Resolve flow from registry
        definition = self._registry.get(flow_id)
        if not definition:
            logger.error("FlowExecutor: flow_id not found in registry: %s", flow_id)
            return FlowResult(
                flow_id=flow_id,
                ok=False,
                steps=[],
                duration_sec=time.time() - start,
            )

        logger.info(
            "FlowExecutor: executing flow '%s' (%d steps, write=%s)",
            flow_id,
            len(definition.steps),
            write,
        )

        # 2. Execute steps in declaration order
        step_results: list[StepResult] = []

        for step in definition.steps:
            step_result = await self._execute_step(
                step, write=write, caller_params=params
            )
            step_results.append(step_result)

            if not step_result.ok and step.required:
                # Required step failed — halt and return immediately
                logger.error(
                    "FlowExecutor: required step '%s' failed in flow '%s' — halting",
                    step.ref_id,
                    flow_id,
                )
                return FlowResult(
                    flow_id=flow_id,
                    ok=False,
                    steps=step_results,
                    duration_sec=time.time() - start,
                )

            if not step_result.ok and not step.required:
                logger.warning(
                    "FlowExecutor: optional step '%s' failed in flow '%s' — continuing",
                    step.ref_id,
                    flow_id,
                )

        duration = time.time() - start
        all_required_passed = all(s.ok for s in step_results if s.required)

        logger.info(
            "FlowExecutor: flow '%s' complete in %.2fs — ok=%s",
            flow_id,
            duration,
            all_required_passed,
        )

        return FlowResult(
            flow_id=flow_id,
            ok=all_required_passed,
            steps=step_results,
            duration_sec=duration,
        )

    # ID: 5ead0cc7-b5bc-4c9c-8d23-242ebf238e24
    async def _execute_step(
        self,
        step: FlowStep,
        write: bool,
        caller_params: dict[str, Any],
    ) -> StepResult:
        """
        Execute a single step — dispatches to ActionExecutor or
        recursively to FlowExecutor depending on step.kind.

        write=False is enforced unconditionally — a step cannot
        escalate to write mode even if its static params request it.
        """
        # Merge params: static step params first, caller params override
        merged_params = {**step.params, **caller_params}

        step_start = time.time()

        if step.kind == StepKind.ACTION:
            return await self._execute_action_step(
                step, write, merged_params, step_start
            )
        elif step.kind == StepKind.FLOW:
            return await self._execute_flow_step(step, write, merged_params, step_start)
        else:
            # Defensive — StepKind is an enum, this should never fire
            logger.error(
                "FlowExecutor: unknown step kind '%s' for step '%s'",
                step.kind,
                step.ref_id,
            )
            return StepResult(
                ref_id=step.ref_id,
                required=step.required,
                ok=False,
                data={"error": f"Unknown step kind: {step.kind}"},
                duration_sec=time.time() - step_start,
                kind=str(step.kind),
            )

    # ID: cb8eea14-5b0e-4d2b-bcb6-ebd45ab9d14f
    async def _execute_action_step(
        self,
        step: FlowStep,
        write: bool,
        params: dict[str, Any],
        step_start: float,
    ) -> StepResult:
        """Dispatch an AtomicAction step via ActionExecutor."""
        from body.atomic.executor import ActionExecutor

        executor = ActionExecutor(self._core_context)

        try:
            action_result = await executor.execute(step.ref_id, write=write, **params)
            return StepResult(
                ref_id=step.ref_id,
                required=step.required,
                ok=action_result.ok,
                data=action_result.data
                if isinstance(action_result.data, dict)
                else {"result": str(action_result.data)},
                duration_sec=action_result.duration_sec,
                kind="action",
            )
        except Exception as exc:
            logger.error(
                "FlowExecutor: action step '%s' raised: %s",
                step.ref_id,
                exc,
                exc_info=True,
            )
            return StepResult(
                ref_id=step.ref_id,
                required=step.required,
                ok=False,
                data={"error": str(exc)},
                duration_sec=time.time() - step_start,
                kind="action",
            )

    # ID: 28e9c338-d7ad-49a5-95de-e91edb324989
    async def _execute_flow_step(
        self,
        step: FlowStep,
        write: bool,
        params: dict[str, Any],
        step_start: float,
    ) -> StepResult:
        """Dispatch a nested Flow step recursively via FlowExecutor."""
        try:
            nested_result = await self.execute(step.ref_id, write=write, **params)
            return StepResult(
                ref_id=step.ref_id,
                required=step.required,
                ok=nested_result.ok,
                data=nested_result.data,
                duration_sec=nested_result.duration_sec,
                kind="flow",
            )
        except Exception as exc:
            logger.error(
                "FlowExecutor: nested flow step '%s' raised: %s",
                step.ref_id,
                exc,
                exc_info=True,
            )
            return StepResult(
                ref_id=step.ref_id,
                required=step.required,
                ok=False,
                data={"error": str(exc)},
                duration_sec=time.time() - step_start,
                kind="flow",
            )
