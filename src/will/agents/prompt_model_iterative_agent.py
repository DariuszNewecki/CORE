# src/will/agents/prompt_model_iterative_agent.py
"""
PromptModelIterativeAgent — Will-tier iterative generation for PromptModel.invoke() paths.

Parallel to IterativeCoderAgent (which wraps CoderAgent for ExecutionTask-based flows).
Use this agent when the generation path uses PromptModel.invoke() with custom context
variables rather than CoderAgent's ContextService pipeline.

This agent carries the iterative loop extracted from body/atomic/build_test_for_symbol_action.py
(ADR-140 D5). The behavioral contract is preserved: same budget source, same prompts,
same IntentGuard acceptance condition, same failure semantics where practical.

Layer: Will. No filesystem writes. No direct database access. Delegates all mutations
to Body actions via the Flow mechanism.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from shared.ai.prompt_model import PromptModel
from shared.infrastructure.intent.generation_budget import load_generation_budget
from shared.logger import getLogger
from shared.utils.test_gen_utils import extract_from_fences, format_violations


if TYPE_CHECKING:
    from shared.protocols.cognitive import CognitiveProtocol

logger = getLogger(__name__)


# ID: 301ade3a-90a9-4762-bd48-2e20760f437c
class GenerationFailedError(Exception):
    """
    Raised by PromptModelIterativeAgent when the generation budget is exhausted
    without producing accepted code.

    Carries the final violations for diagnostic logging.
    """

    def __init__(
        self,
        step_ref: str,
        attempts: int,
        violations: list[dict],
        reason: str = "budget_exhausted",
    ) -> None:
        self.step_ref = step_ref
        self.attempts = attempts
        self.violations = violations
        self.reason = reason
        super().__init__(
            f"Generation failed for {step_ref!r} after {attempts} attempt(s): {reason}"
        )


# ID: 8f90727e-667e-439c-9f71-f710cdc95df5
class PromptModelIterativeAgent:
    """
    Will-tier iterative generation agent for direct PromptModel.invoke() paths.

    Loop: generate → IntentGuard → feed violations back → repeat, up to the
    governed cap in generation_budget.yaml.

    Accepts pre-built context dicts — context preparation (symbol extraction,
    module path derivation) is the caller's responsibility. This agent only
    drives the generate → validate → repair loop.
    """

    # ID: 5658a1c0-597f-47f0-a43e-6af718c497d1
    async def generate(
        self,
        prompt_name: str,
        repair_prompt_name: str,
        context: dict[str, Any],
        target_path: str,
        cognitive_service: CognitiveProtocol,
        repo_root: Path,
        step_ref: str = "generate",
        task_type: str = "test_generation",
    ) -> str:
        """
        Run the iterative generate → validate → repair loop.

        Args:
            prompt_name:         Initial generation prompt name (e.g.
                                 "context_aware_test_gen").
            repair_prompt_name:  Repair iteration prompt name (e.g.
                                 "context_aware_test_gen_repair").
            context:             Base context dict for the initial prompt.
                                 Must include all required inputs for prompt_name.
                                 Repair iterations extend this with
                                 violations_summary and previous_code.
            target_path:         Repo-relative path of the file to be written.
                                 Passed to IntentGuard for path-level validation.
            cognitive_service:   CognitiveProtocol instance for LLM calls.
            repo_root:           Absolute repo root path for IntentGuard.
            step_ref:            Identifier for logging/error attribution.
            task_type:           Budget lookup key in generation_budget.yaml.

        Returns:
            The first generated code string that passes IntentGuard.

        Raises:
            GenerationFailedError: If the governed budget is exhausted without
                                   an accepted result, or if the wall-clock cap
                                   is hit.
        """
        from body.governance.intent_guard import get_intent_guard

        start = time.time()
        budget = load_generation_budget().for_task_type(task_type)
        max_iterations = budget.max_iterations
        wall_clock_cap = budget.wall_clock_cap_secs

        logger.info(
            "PromptModelIterativeAgent[%s]: starting — cap=%d iterations, %ds wall-clock",
            step_ref,
            max_iterations,
            wall_clock_cap,
        )

        # Load initial prompt and acquire the LLM client.
        try:
            model = PromptModel.load(prompt_name)
            generator = await cognitive_service.aget_client_for_role(
                model.manifest.role
            )
        except Exception as exc:
            logger.error(
                "PromptModelIterativeAgent[%s]: failed to load prompt/client: %s",
                step_ref,
                exc,
            )
            raise GenerationFailedError(
                step_ref=step_ref,
                attempts=0,
                violations=[],
                reason=f"prompt_or_client_init_failed: {exc}",
            ) from exc

        intent_guard = get_intent_guard(repo_path=repo_root)

        previous_code: str | None = None
        last_violations: list[dict] = []

        for attempt in range(max_iterations):
            is_repair = attempt > 0

            # Invoke LLM — initial or repair prompt.
            try:
                if is_repair:
                    repair_model = PromptModel.load(repair_prompt_name)
                    raw_response = await asyncio.wait_for(
                        repair_model.invoke(
                            context={
                                **context,
                                "violations_summary": format_violations(
                                    last_violations
                                ),
                                "previous_code": previous_code or "",
                            },
                            client=generator,
                            user_id=f"{step_ref}_repair",
                        ),
                        timeout=wall_clock_cap,
                    )
                else:
                    raw_response = await asyncio.wait_for(
                        model.invoke(
                            context=context,
                            client=generator,
                            user_id=step_ref,
                        ),
                        timeout=wall_clock_cap,
                    )
            except TimeoutError:
                logger.warning(
                    "PromptModelIterativeAgent[%s]: wall-clock cap hit on attempt %d/%d "
                    "(%.1fs elapsed)",
                    step_ref,
                    attempt + 1,
                    max_iterations,
                    time.time() - start,
                )
                raise GenerationFailedError(
                    step_ref=step_ref,
                    attempts=attempt + 1,
                    violations=last_violations,
                    reason="wall_clock_cap_exceeded",
                )
            except Exception as exc:
                logger.error(
                    "PromptModelIterativeAgent[%s]: LLM invocation failed on attempt %d: %s",
                    step_ref,
                    attempt + 1,
                    exc,
                )
                raise GenerationFailedError(
                    step_ref=step_ref,
                    attempts=attempt + 1,
                    violations=last_violations,
                    reason=f"llm_invocation_failed: {exc}",
                ) from exc

            # Extract code from fences.
            generated_code = extract_from_fences(raw_response)
            if not generated_code:
                if attempt < max_iterations - 1:
                    last_violations = [
                        {
                            "rule_name": "output.no_code_fence",
                            "message": "LLM response contained no ```python fences",
                        }
                    ]
                    previous_code = raw_response[:500]
                    logger.warning(
                        "PromptModelIterativeAgent[%s]: no fences on attempt %d/%d — retrying",
                        step_ref,
                        attempt + 1,
                        max_iterations,
                    )
                    continue
                raise GenerationFailedError(
                    step_ref=step_ref,
                    attempts=attempt + 1,
                    violations=[{"rule_name": "output.no_code_fence"}],
                    reason="no_code_fence",
                )

            # IntentGuard validation.
            try:
                validation = intent_guard.validate_generated_code(
                    code=generated_code,
                    pattern_id="test_file",
                    component_type="test",
                    target_path=target_path,
                )
            except Exception as exc:
                logger.error(
                    "PromptModelIterativeAgent[%s]: IntentGuard raised on attempt %d: %s",
                    step_ref,
                    attempt + 1,
                    exc,
                    exc_info=True,
                )
                raise GenerationFailedError(
                    step_ref=step_ref,
                    attempts=attempt + 1,
                    violations=last_violations,
                    reason=f"intent_guard_raised: {exc}",
                ) from exc

            if validation.is_valid:
                if attempt > 0:
                    logger.info(
                        "PromptModelIterativeAgent[%s]: accepted on attempt %d/%d",
                        step_ref,
                        attempt + 1,
                        max_iterations,
                    )
                return generated_code

            # Validation failed — accumulate violations for the repair prompt.
            last_violations = [
                {
                    "rule_name": getattr(v, "rule_name", "unknown"),
                    "message": getattr(v, "message", ""),
                    "severity": getattr(v, "severity", "error"),
                }
                for v in validation.violations
            ]
            previous_code = generated_code

            if attempt == max_iterations - 1:
                raise GenerationFailedError(
                    step_ref=step_ref,
                    attempts=attempt + 1,
                    violations=last_violations,
                    reason="intent_guard_violations",
                )

            logger.info(
                "PromptModelIterativeAgent[%s]: attempt %d/%d — %d violations, retrying",
                step_ref,
                attempt + 1,
                max_iterations,
                len(last_violations),
            )

        # Should not reach here (loop always breaks or raises), but satisfy type checker.
        raise GenerationFailedError(
            step_ref=step_ref,
            attempts=max_iterations,
            violations=last_violations,
            reason="budget_exhausted",
        )
