# src/shared/protocols/cognitive_flow_delegate.py
"""
CognitiveFlowDelegate — the Body/Will boundary contract for Flow cognitive steps.

Body's FlowExecutor depends on this protocol from shared. Will-tier implementations
(TestGenCognitiveDelegate, etc.) are injected at the ProposalExecutor level. Body
never imports Will implementations directly.

This is the Will→Body direction mirror of ActionExecutorProtocol (executor.py):
  ActionExecutorProtocol  — Will calls Body mutations via shared protocol
  CognitiveFlowDelegate   — Body routes cognitive steps to Will via shared protocol

ADR-140 D3.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


# ID: 07b8664c-4ee7-4069-904e-5d5190bde308
class CognitiveStepError(Exception):
    """
    Raised by a CognitiveFlowDelegate when a cognitive step cannot be executed.

    Carries the step_ref that failed. FlowExecutor catches this and converts it
    into a failed StepResult — never propagates to the caller.
    """

    def __init__(self, step_ref: str, reason: str) -> None:
        self.step_ref = step_ref
        self.reason = reason
        super().__init__(f"Cognitive step {step_ref!r} failed: {reason}")


@runtime_checkable
# ID: 97c2ced6-e633-4aa9-adda-80f79c425d25
class CognitiveFlowDelegate(Protocol):
    """
    Protocol for Will-tier implementations that execute cognitive Flow steps.

    Body's FlowExecutor calls this protocol when it encounters a step with
    kind: cognitive. The delegate performs the actual LLM orchestration
    (prompting, repair loops, acceptance checks) and returns a dict of
    output keys to be threaded into downstream steps as params.

    Implementations live in src/will/agents/. Each implementation handles
    one or more step_ref identifiers specific to its cognitive capability.

    Contract:
    - Returns a dict whose keys match the step's declared produces list.
    - Raises CognitiveStepError on unknown step_ref or generation failure.
    - Must not write to the filesystem — that is the downstream action's job.
    - Must not call ActionExecutor — cognitive steps are read/think only.
    """

    # ID: a8309080-c70d-4948-bd70-1ecba24434b3
    async def execute_cognitive_step(
        self,
        step_ref: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Execute a cognitive step identified by step_ref.

        Args:
            step_ref: Stable identifier for the cognitive operation (e.g.
                      "generate.test_snippet"). Not a registered action_id.
            params:   Runtime parameters forwarded by FlowExecutor (filtered
                      by the step's consumes declaration before arriving here).

        Returns:
            A dict whose keys match the step's declared produces list.
            FlowExecutor validates that all declared keys are present and
            threads them into accumulated_params for downstream steps.

        Raises:
            CognitiveStepError: If step_ref is unknown or generation fails
                                after exhausting the governed budget.
        """
        ...
