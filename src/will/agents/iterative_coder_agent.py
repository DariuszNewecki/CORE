# src/will/agents/iterative_coder_agent.py
"""
IterativeCoderAgent — Will-tier orchestration wrapper around CoderAgent (ADR-135 D2).

Provides iterative generation: loops over (generate → accept → feed violations back)
up to the governed iteration cap declared in generation_budget.yaml. The acceptance
predicate is injectable (AcceptanceCondition) so callers can compose IntentGuard,
pytest, and audit checks independently of the generation loop itself.

Architecture note on flow.build_test_for_symbol (ADR-140 D5 closure):
  The iterative loop for flow.build_test_for_symbol was previously in Body tier as
  acknowledged debt (ADR-135 D2). It has been extracted to PromptModelIterativeAgent
  (will/agents/prompt_model_iterative_agent.py), which handles PromptModel.invoke()
  paths. IterativeCoderAgent (this class) remains the primitive for CoderAgent-based
  flows that route through CoderAgent.generate_or_repair. The two coexist; neither
  deprecates the other.

Layer: Will. No subprocess. No direct database access. Delegates I/O to Body.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from shared.infrastructure.intent.generation_budget import load_generation_budget
from shared.logger import getLogger
from shared.models.generation_mode import GenerationMode


if TYPE_CHECKING:
    from shared.models import ExecutionTask
    from will.agents.acceptance.conditions import AcceptanceCondition
    from will.agents.coder_agent import CoderAgent

logger = getLogger(__name__)


@dataclass
# ID: 54317c2a-839f-4f96-b0a3-f6d94521c4c4
class IterationResult:
    """Outcome of IterativeCoderAgent.generate_until_accepted."""

    code: str
    iterations_used: int
    final_violations: list[str] = field(default_factory=list)
    accepted: bool = False


# ID: 1ac85e52-eaab-48cd-bf79-6b35a9dcfc2f
class IterativeCoderAgent:
    """
    Iterative generation orchestrator wrapping CoderAgent (ADR-135 D2).

    Loops over:
      1. Call coder_agent.generate_or_repair(task, goal, pain_signal, previous_code)
      2. Evaluate acceptance via the injected AcceptanceCondition
      3. If accepted → return IterationResult(accepted=True)
      4. If not accepted → feed violation_summary as pain_signal, increment attempt
      5. On cap exhaustion → return IterationResult(accepted=False)

    The iteration cap is governed by generation_budget.yaml and CANNOT be exceeded
    by the caller — if caller_cap > governed cap, the governed cap wins.
    """

    def __init__(self, coder_agent: CoderAgent) -> None:
        self._coder_agent = coder_agent

    # ID: f2e776ca-e6a8-41aa-9e75-feba78754df3
    async def generate_until_accepted(
        self,
        task: ExecutionTask,
        goal: str,
        acceptance: AcceptanceCondition,
        caller_cap: int | None = None,
        task_type: str = "test_generation",
    ) -> IterationResult:
        """
        Generate code iteratively until the acceptance condition is met or the cap is hit.

        Args:
            task:       ExecutionTask describing the generation goal.
            goal:       Human-readable goal string passed to CoderAgent.
            acceptance: Predicate that evaluates each generated code string.
            caller_cap: Optional caller-supplied cap. Governed cap from
                        generation_budget.yaml wins if caller_cap exceeds it.
            task_type:  Used to look up the iteration budget. Defaults to
                        'test_generation'.

        Returns:
            IterationResult — always. Never raises.
        """
        budget = load_generation_budget().for_task_type(task_type)
        governed_cap = budget.max_iterations
        wall_clock_cap = budget.wall_clock_cap_secs

        if caller_cap is not None and caller_cap > governed_cap:
            logger.warning(
                "IterativeCoderAgent: caller_cap=%d exceeds governed cap=%d — using %d",
                caller_cap,
                governed_cap,
                governed_cap,
            )
        effective_cap = (
            min(caller_cap, governed_cap) if caller_cap is not None else governed_cap
        )

        logger.info(
            "IterativeCoderAgent: starting iterative generation (cap=%d, wall_clock=%ds)",
            effective_cap,
            wall_clock_cap,
        )

        pain_signal: str | None = None
        previous_code: str | None = None
        last_violations: list[str] = []

        for attempt in range(effective_cap):
            try:
                code = await asyncio.wait_for(
                    self._coder_agent.generate_or_repair(
                        task=task,
                        goal=goal,
                        pain_signal=pain_signal,
                        previous_code=previous_code,
                    ),
                    timeout=wall_clock_cap,
                )
            except TimeoutError:
                logger.warning(
                    "IterativeCoderAgent: wall-clock cap hit on attempt %d/%d",
                    attempt + 1,
                    effective_cap,
                )
                return IterationResult(
                    code=previous_code or "",
                    iterations_used=attempt + 1,
                    final_violations=last_violations,
                    accepted=False,
                )
            except Exception as exc:
                logger.error(
                    "IterativeCoderAgent: CoderAgent raised on attempt %d: %s",
                    attempt + 1,
                    exc,
                )
                return IterationResult(
                    code=previous_code or "",
                    iterations_used=attempt + 1,
                    final_violations=[str(exc)],
                    accepted=False,
                )

            try:
                result = await acceptance.evaluate(code, task)
            except Exception as exc:
                logger.error(
                    "IterativeCoderAgent: acceptance.evaluate raised on attempt %d: %s",
                    attempt + 1,
                    exc,
                )
                return IterationResult(
                    code=code,
                    iterations_used=attempt + 1,
                    final_violations=[str(exc)],
                    accepted=False,
                )

            if result.accepted:
                logger.info(
                    "IterativeCoderAgent: accepted on attempt %d/%d",
                    attempt + 1,
                    effective_cap,
                )
                return IterationResult(
                    code=code,
                    iterations_used=attempt + 1,
                    final_violations=[],
                    accepted=True,
                )

            pain_signal = result.violation_summary
            previous_code = code
            last_violations = result.violations
            logger.info(
                "IterativeCoderAgent: attempt %d/%d rejected (%d violations) — retrying",
                attempt + 1,
                effective_cap,
                len(last_violations),
            )

        return IterationResult(
            code=previous_code or "",
            iterations_used=effective_cap,
            final_violations=last_violations,
            accepted=False,
        )

    @property
    # ID: 8cde8b4e-4317-4a0f-934b-5e2c232aa41c
    def generation_mode(self) -> GenerationMode:
        return GenerationMode.ITERATIVE
