# src/will/agents/coder_agent.py
"""
Provides the CoderAgent, a specialist AI agent responsible for orchestrating
code generation, validation, and self-correction tasks within the CORE system.

UPGRADED (A3 -> A2 Enhanced): Now fully autonomous with modular architecture.
- Enforces design patterns via IntentGuard
- Detects runtime/import errors
- Self-corrects using SymbolFinder (Knowledge Graph) lookup
- Modular design following separation_of_concerns principle
- A2 NEW: Enhanced context with code examples and reasoning
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from services.clients.qdrant_client import QdrantService
from shared.config import settings
from shared.logger import getLogger
from shared.models import ExecutionTask

from will.agents.code_generation import (
    CodeGenerator,
    CorrectionEngine,
    PatternValidator,
)
from will.orchestration.cognitive_service import CognitiveService
from will.orchestration.decision_tracer import DecisionTracer
from will.orchestration.intent_guard import IntentGuard
from will.orchestration.prompt_pipeline import PromptPipeline
from will.orchestration.validation_pipeline import validate_code_async
from will.tools.architectural_context_builder import ArchitecturalContextBuilder
from will.tools.module_anchor_generator import ModuleAnchorGenerator
from will.tools.policy_vectorizer import PolicyVectorizer

if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext

logger = getLogger(__name__)


# ID: 77a4efd7-1a64-460d-a478-031611786403
class CodeGenerationError(Exception):
    """Raised when code generation fails, carrying the invalid code for debugging."""

    def __init__(self, message: str, code: str | None = None):
        super().__init__(message)
        self.code = code


# ID: e1d31b9b-a273-45a9-afef-62d0336db1c9
class CoderAgent:
    """
    Orchestrates code generation with constitutional governance.
    Delegates to specialist components following separation of concerns.

    A2 Enhanced: Now provides richer context with code examples and reasoning.
    """

    def __init__(
        self,
        cognitive_service: CognitiveService,
        prompt_pipeline: PromptPipeline,
        auditor_context: AuditorContext,
        qdrant_service: QdrantService | None = None,
    ):
        """
        Initialize the CoderAgent with specialist components.

        Args:
            cognitive_service: LLM orchestration service
            prompt_pipeline: Prompt enhancement pipeline
            auditor_context: Constitutional auditing context
            qdrant_service: Optional vector database for semantic features
        """
        self.cognitive_service = cognitive_service
        self.prompt_pipeline = prompt_pipeline
        self.auditor_context = auditor_context
        self.repo_root = settings.REPO_PATH
        self.tracer = DecisionTracer()

        # Load agent behavior config
        try:
            agent_policy = settings.load("charter.policies.agent_governance")
        except Exception:
            agent_policy = {}

        agent_behavior = agent_policy.get("execution_agent", {})
        self.max_correction_attempts = agent_behavior.get("max_correction_attempts", 2)

        # Initialize specialist components
        intent_guard = IntentGuard(self.repo_root)
        self.pattern_validator = PatternValidator(intent_guard)
        self.correction_engine = CorrectionEngine(
            cognitive_service, auditor_context, self.tracer
        )

        # Initialize semantic infrastructure if available
        context_builder = None
        if qdrant_service:
            try:
                policy_vectorizer = PolicyVectorizer(
                    self.repo_root, cognitive_service, qdrant_service
                )
                module_anchor_generator = ModuleAnchorGenerator(
                    self.repo_root, cognitive_service, qdrant_service
                )
                # A2 ENHANCED: Pass cognitive_service and qdrant_service for code examples
                context_builder = ArchitecturalContextBuilder(
                    policy_vectorizer,
                    module_anchor_generator,
                    cognitive_service=cognitive_service,
                    qdrant_service=qdrant_service,
                )
                logger.info(
                    "CoderAgent initialized with A2 Enhanced Semantic Infrastructure."
                )
            except Exception as e:
                logger.warning(
                    f"Failed to initialize Semantic Infrastructure: {e}. "
                    "Falling back to standard generation."
                )

        self.code_generator = CodeGenerator(
            cognitive_service, prompt_pipeline, self.tracer, context_builder
        )

    # ID: 284cb9fb-2dfb-4017-949e-647ed1fc1951
    async def generate_and_validate_code_for_task(
        self,
        task: ExecutionTask,
        high_level_goal: str,
        context_str: str,
    ) -> str:
        """
        Main entry point: generates code and validates it through multiple phases.

        Args:
            task: Execution task with parameters
            high_level_goal: High-level goal description
            context_str: Additional context string

        Returns:
            Valid, constitutionally-compliant Python code

        Raises:
            CodeGenerationError: If generation or validation fails
        """
        try:
            # Infer pattern requirements
            pattern_id = self.pattern_validator.infer_pattern_id(task)
            component_type = self.pattern_validator.infer_component_type(task)
            pattern_requirements = self.pattern_validator.get_pattern_requirements(
                pattern_id
            )

            # Generate initial code
            current_code = await self.code_generator.generate_code(
                task, high_level_goal, context_str, pattern_id, pattern_requirements
            )

            # Validation loop with self-correction
            for attempt in range(self.max_correction_attempts + 1):
                logger.info("  -> Validation attempt %s...", attempt + 1)

                # PHASE 1: Pattern Validation
                (
                    pattern_approved,
                    pattern_violations,
                ) = await self.pattern_validator.validate_code(
                    current_code, pattern_id, component_type, task.params.file_path
                )

                if not pattern_approved:
                    if attempt >= self.max_correction_attempts:
                        self.tracer.save_trace()
                        raise CodeGenerationError(
                            f"Pattern violations after {self.max_correction_attempts + 1} attempts",
                            code=current_code,
                        )

                    logger.warning(
                        "  -> ⚠️ Pattern violations found. Attempting correction..."
                    )
                    correction_result = (
                        await self.correction_engine.attempt_pattern_correction(
                            task,
                            current_code,
                            pattern_violations,
                            pattern_id,
                            pattern_requirements,
                            high_level_goal,
                        )
                    )

                    if correction_result.get("status") == "success":
                        current_code = correction_result["code"]
                        continue
                    else:
                        self.tracer.save_trace()
                        raise CodeGenerationError(
                            f"Pattern correction failed: {correction_result.get('message')}",
                            code=current_code,
                        )

                logger.info(f"  -> ✅ Pattern validation passed: {pattern_id}")

                # PHASE 2: Constitutional & Runtime Validation
                validation_result = await validate_code_async(
                    task.params.file_path,
                    current_code,
                    auditor_context=self.auditor_context,
                )

                if validation_result["status"] == "clean":
                    logger.info("  -> ✅ Constitutional validation passed.")
                    self.tracer.save_trace()
                    return validation_result["code"]

                if attempt >= self.max_correction_attempts:
                    self.tracer.save_trace()
                    raise CodeGenerationError(
                        f"Constitutional validation failed after {self.max_correction_attempts + 1} attempts.",
                        code=current_code,
                    )

                logger.warning(
                    "  -> ⚠️ Constitutional violations found. Attempting self-correction."
                )

                # Extract runtime errors if present
                runtime_error = self._extract_runtime_error(validation_result)

                correction_result = (
                    await self.correction_engine.attempt_constitutional_correction(
                        task,
                        current_code,
                        validation_result,
                        high_level_goal,
                        runtime_error,
                    )
                )

                if correction_result.get("status") == "success":
                    logger.info("  -> ✅ Self-correction generated a potential fix.")
                    current_code = correction_result["code"]
                else:
                    self.tracer.save_trace()
                    raise CodeGenerationError(
                        f"Self-correction failed: {correction_result.get('message')}",
                        code=current_code,
                    )

            self.tracer.save_trace()
            raise CodeGenerationError(
                "Could not produce valid code after all attempts.", code=current_code
            )

        except Exception as e:
            self.tracer.save_trace()
            raise

    def _extract_runtime_error(self, validation_result: dict) -> str:
        """Extract runtime error details from validation result."""
        for v in validation_result.get("violations", []):
            if v.get("check_id") == "runtime.tests.failed":
                context_details = v.get("context", {}).get("details", "")
                if context_details:
                    return context_details
                elif "details" in v:
                    return v["details"]
        return ""
