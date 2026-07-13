# src/will/agents/test_gen_cognitive_delegate.py
"""
TestGenCognitiveDelegate — Will-tier CognitiveFlowDelegate for flow.build_test_for_symbol.

Implements shared.protocols.CognitiveFlowDelegate for the "test_generation" cognitive
capability. Handles the "generate.test_snippet" cognitive step by:
  1. Extracting symbol source code via AST (prompt-grounding context)
  2. Deriving the importable module path
  3. Computing the target test file path
  4. Running PromptModelIterativeAgent with the iterative generate → validate → repair loop
  5. Returning {"generated_code": <accepted code>} for FlowExecutor to thread downstream

ADR-140 D6.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from shared.infrastructure.intent.test_coverage_paths import source_to_test_path
from shared.logger import getLogger
from shared.protocols.cognitive_flow_delegate import CognitiveStepError
from shared.utils.test_gen_utils import (
    derive_module_path,
    extract_constructor_signature,
    extract_symbol_code,
)
from will.agents.prompt_model_iterative_agent import (
    GenerationFailedError,
    PromptModelIterativeAgent,
)


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)

_INITIAL_PROMPT = "context_aware_test_gen"
_REPAIR_PROMPT = "context_aware_test_gen_repair"


# ID: 901c0aa6-64b0-47cf-9105-a88675708717
class TestGenCognitiveDelegate:
    """
    CognitiveFlowDelegate implementation for the test_generation cognitive capability.

    Handles the "generate.test_snippet" step declared in flow.build_test_for_symbol.yaml.
    Injected into FlowExecutor by ProposalExecutor._build_cognitive_delegate() when
    flow_def.cognitive_capability == "test_generation" (ADR-140 D9).
    """

    def __init__(self, core_context: CoreContext) -> None:
        self._core_context = core_context
        self._agent = PromptModelIterativeAgent()

    # ID: d128250b-8dcd-42f6-ab38-e85e11cba628
    async def execute_cognitive_step(
        self,
        step_ref: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Execute a cognitive step for test generation.

        Supported step_refs:
          "generate.test_snippet" — iterative LLM generation of a pytest test snippet.

        Raises CognitiveStepError on unknown step_ref or generation failure.
        """
        if step_ref == "generate.test_snippet":
            return await self._generate_test_snippet(params)

        raise CognitiveStepError(
            step_ref=step_ref,
            reason=f"TestGenCognitiveDelegate does not handle step_ref {step_ref!r}",
        )

    async def _generate_test_snippet(self, params: dict[str, Any]) -> dict[str, Any]:
        """Generate one accepted pytest test snippet for the given symbol."""
        source_file: str = params["source_file"]
        symbol_name: str = params["symbol_name"]
        signature: str = params.get("signature", "")

        repo_root: Path = self._core_context.git_service.repo_path
        source_path = repo_root / source_file

        # Resolve test target path (needed for IntentGuard in the agent).
        try:
            target_path = source_to_test_path(source_file)
        except ValueError as exc:
            raise CognitiveStepError(
                step_ref="generate.test_snippet",
                reason=f"Cannot derive test path: {exc}",
            ) from exc

        # Extract symbol source code for prompt grounding.
        symbol_code = extract_symbol_code(source_path, symbol_name)
        if not symbol_code:
            symbol_code = f"# {signature}"

        # Method-level symbols (dotted ClassName.method_name) never include
        # the containing class's constructor in symbol_code above — the
        # method body alone doesn't say whether the class needs constructor
        # arguments. Prepend it when present so instantiation isn't a guess.
        class_name, _dot, method_name = symbol_name.partition(".")
        if method_name:
            constructor_code = extract_constructor_signature(source_path, class_name)
            if constructor_code:
                symbol_code = (
                    f"# {class_name}.__init__ (constructor context for "
                    f"instantiating the class under test):\n"
                    f"{constructor_code}\n\n"
                    f"# Method under test:\n{symbol_code}"
                )

        module_path = derive_module_path(source_file)

        # Acquire cognitive service (prefer pre-warmed; fall back to registry).
        cognitive_service = self._core_context.cognitive_service
        if cognitive_service is None:
            try:
                cognitive_service = (
                    await self._core_context.registry.get_cognitive_service()
                )
            except Exception as exc:
                raise CognitiveStepError(
                    step_ref="generate.test_snippet",
                    reason=f"Cognitive service unavailable: {exc}",
                ) from exc

        context = {
            "file_path": source_file,
            "symbol_name": symbol_name,
            "symbol_code": symbol_code,
            "module_path": module_path,
        }

        try:
            generated_code = await self._agent.generate(
                prompt_name=_INITIAL_PROMPT,
                repair_prompt_name=_REPAIR_PROMPT,
                context=context,
                target_path=target_path,
                cognitive_service=cognitive_service,
                repo_root=repo_root,
                step_ref="generate.test_snippet",
                task_type="test_generation",
            )
        except GenerationFailedError as exc:
            logger.error(
                "TestGenCognitiveDelegate: generation failed for %s::%s — %s "
                "(%d attempt(s), %d violations)",
                source_file,
                symbol_name,
                exc.reason,
                exc.attempts,
                len(exc.violations),
            )
            raise CognitiveStepError(
                step_ref="generate.test_snippet",
                reason=exc.reason,
            ) from exc

        logger.info(
            "TestGenCognitiveDelegate: generated test snippet for %s::%s",
            source_file,
            symbol_name,
        )
        return {"generated_code": generated_code}
