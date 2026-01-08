# src/will/agents/conversational/agent.py

"""
ConversationalAgent - End-user interface to CORE's capabilities.

This agent provides a natural language interface for users to interact with
CORE without needing to understand internal commands or architecture.

V2 (v2.2.0): Now uses Universal Workflow Pattern
  - INTERPRET: RequestInterpreter parses user message → TaskStructure
  - ANALYZE: ContextBuilder extracts relevant context
  - GENERATE: LLM generates response
  - (Future phases: STRATEGIZE, EVALUATE, DECIDE for execution)

Phase 1 (Current): Read-only information retrieval
  - Extract minimal context using ContextBuilder
  - Send to LLM for analysis
  - Return natural language response
  - NO proposals, NO execution

Phase 2 (Future): Proposal generation
  - Parse LLM responses into actionable proposals
  - Submit through Mind governance

Phase 3 (Future): Full autonomous execution
  - Execute approved proposals via Body
  - Report results conversationally

Constitutional boundaries:
  - All context extraction governed by Mind policies
  - All proposals validated by Mind governance
  - All execution via Body atomic actions
"""

from __future__ import annotations

from typing import Any

from shared.infrastructure.context.builder import ContextBuilder
from shared.logger import getLogger
from shared.universal import get_deterministic_id
from will.interpreters import NaturalLanguageInterpreter, TaskType
from will.orchestration.cognitive_service import CognitiveService
from will.orchestration.decision_tracer import DecisionTracer

from .helpers import (
    _build_llm_prompt,
    _format_context_items,
)


logger = getLogger(__name__)


# ID: a5e19b5b-cb22-43a4-8c76-6d708922408b
class ConversationalAgent:
    """
    Orchestrates conversational interaction between user and CORE.

    V2 (v2.2.0): Uses Universal Workflow Pattern with RequestInterpreter.
    Phase 1: Information retrieval only - helps users understand their codebase
    without making any modifications.
    """

    def __init__(
        self, context_builder: ContextBuilder, cognitive_service: CognitiveService
    ):
        """
        Initialize conversational agent.

        Args:
            context_builder: Service to extract minimal context packages
            cognitive_service: Service to communicate with LLM
        """
        self.context_builder = context_builder
        self.cognitive_service = cognitive_service
        self.interpreter = NaturalLanguageInterpreter()
        self.tracer = DecisionTracer()
        logger.info("ConversationalAgent initialized (V2 - Universal Workflow Pattern)")

    # ID: f5917f41-6465-4e8e-9a4e-0eb4005e7f5f
    async def process_message(self, user_message: str) -> str:
        """
        Process a user message and return a natural language response.

        V2 Flow:
        1. INTERPRET: Parse user message → TaskStructure
        2. ANALYZE: Extract context based on task
        3. GENERATE: LLM generates response
        4. Return natural language response

        Args:
            user_message: Natural language query from user

        Returns:
            Natural language response from CORE

        Example:
            >>> response = await agent.process_message("what does ContextBuilder do?")
            >>> logger.info(response)
            ContextBuilder is responsible for extracting minimal context packages...
        """
        logger.info("Processing user message: %s...", user_message[:100])

        try:
            # ============================================================
            # INTERPRET PHASE (NEW in v2.2.0)
            # ============================================================
            logger.info("🔍 INTERPRET: Parsing user intent...")
            interpret_result = await self.interpreter.execute(user_message=user_message)

            if not interpret_result.ok:
                return "❌ Sorry, I couldn't understand your request. Can you rephrase?"

            task = interpret_result.data["task"]
            logger.info(
                "   → Task Type: %s (confidence: %.2f)",
                task.task_type.value,
                task.confidence,
            )

            # Low confidence → ask for clarification
            if task.confidence < 0.4:
                return (
                    "I'm not sure I understood that correctly. "
                    "Could you be more specific about what you'd like me to do?"
                )

            # ============================================================
            # ANALYZE PHASE
            # ============================================================
            logger.info("📊 ANALYZE: Extracting context...")
            task_spec = self._build_task_spec_from_task(task)
            context_package = await self.context_builder.build_for_task(task_spec)
            logger.info(
                "   → Found %d context items", len(context_package.get("context", []))
            )

            # ============================================================
            # GENERATE PHASE
            # ============================================================
            logger.info("💬 GENERATE: Creating response...")
            prompt = self._build_llm_prompt(user_message, context_package, task)
            client = await self.cognitive_service.aget_client_for_role("Planner")
            llm_response = await client.make_request_async(prompt)
            response_text = llm_response.strip()

            # Trace the decision
            self.tracer.record(
                agent=self.__class__.__name__,
                decision_type="conversational_response",
                rationale=f"Interpreted as {task.task_type.value}, extracted context, generated response",
                chosen_action="Returned conversational response to user",
                context={
                    "task_type": task.task_type.value,
                    "confidence": task.confidence,
                    "targets": task.targets,
                },
                confidence=0.9,
            )

            return response_text

        except Exception as e:
            logger.error("Failed to process message: %s", e, exc_info=True)
            self.tracer.record(
                agent=self.__class__.__name__,
                decision_type="conversational_response",
                rationale="Processing failed",
                chosen_action=f"Error: {e!s}",
                confidence=0.0,
            )
            return f"❌ Error processing your message: {e!s}"

    def _build_task_spec_from_task(self, task) -> dict[str, Any]:
        """
        Convert TaskStructure → ContextBuilder task spec.

        This bridges INTERPRET output → ANALYZE input.
        Maintains the sophisticated structure from the original implementation.

        Args:
            task: TaskStructure from RequestInterpreter

        Returns:
            Task spec for ContextBuilder with full metadata
        """
        # Generate deterministic task ID for caching
        task_hash = get_deterministic_id(task.intent)

        # Map TaskType → ContextBuilder task type
        task_type_map = {
            TaskType.QUERY: "conversational",
            TaskType.ANALYZE: "conversational",
            TaskType.EXPLAIN: "conversational",
            TaskType.REFACTOR: "code_modification",
            TaskType.FIX: "code_modification",
            TaskType.GENERATE: "code_generation",
            TaskType.TEST: "test_generation",
        }

        return {
            "task_id": f"chat-{task_hash & 0xFFFFFFFF:08x}",
            "task_type": task_type_map.get(task.task_type, "conversational"),
            "summary": task.intent,
            "privacy": "local_only",
            "scope": {
                "include": task.targets,  # Use targets from interpreter
                "exclude": [],
                "globs": [],
                "roots": [],
                "traversal_depth": 1,  # Keep it minimal for Phase 1
            },
            "constraints": {
                "max_tokens": 50000,  # Don't overwhelm the LLM
                "max_items": 30,  # Keep context focused
            },
        }

    def _build_llm_prompt(
        self, user_message: str, context_package: dict[str, Any], task
    ) -> str:
        """
        Build the prompt to send to the LLM.

        Includes:
        - System context about CORE
        - Task interpretation metadata
        - The extracted context package
        - The user's question
        - Instructions for the LLM

        Args:
            user_message: Original user query
            context_package: Minimal context from ContextBuilder
            task: TaskStructure from interpreter

        Returns:
            Complete prompt for LLM
        """
        # Add task interpretation to prompt context
        task_context = f"""
Task Interpretation:
- Type: {task.task_type.value}
- Targets: {', '.join(task.targets) if task.targets else 'none specified'}
- Confidence: {task.confidence:.2f}
"""

        return _build_llm_prompt(
            user_message, context_package, self._format_context_items, task_context
        )

    def _format_context_items(self, items: list[dict[str, Any]]) -> str:
        """
        Format context items into readable text for LLM.

        Args:
            items: List of context items from ContextPackage

        Returns:
            Formatted string representation
        """
        return _format_context_items(items)
