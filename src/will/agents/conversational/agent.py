# src/will/agents/conversational/agent.py

"""
ConversationalAgent - End-user interface to CORE's capabilities.

This agent provides a natural language interface for users to interact with
CORE without needing to understand internal commands or architecture.

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
from will.orchestration.cognitive_service import CognitiveService
from will.orchestration.decision_tracer import DecisionTracer

from .helpers import (
    _build_llm_prompt,
    _create_task_spec,
    _extract_keywords,
    _format_context_items,
)


logger = getLogger(__name__)


# ID: a5e19b5b-cb22-43a4-8c76-6d708922408b
class ConversationalAgent:
    """
    Orchestrates conversational interaction between user and CORE.

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
        self.tracer = DecisionTracer()
        logger.info("ConversationalAgent initialized (Phase 1: read-only)")

    # ID: f5917f41-6465-4e8e-9a4e-0eb4005e7f5f
    async def process_message(self, user_message: str) -> str:
        """
        Process a user message and return a natural language response.

        Phase 1: Extract context + ask LLM, no modifications.

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
            task_spec = self._create_task_spec(user_message)
            logger.info("Extracting context package...")
            context_package = await self.context_builder.build_for_task(task_spec)
            prompt = self._build_llm_prompt(user_message, context_package)
            logger.info("Sending to LLM for analysis...")
            client = await self.cognitive_service.aget_client_for_role("Planner")
            llm_response = await client.make_request_async(prompt)
            response_text = llm_response.strip()
            self.tracer.record(
                agent=self.__class__.__name__,
                decision_type="task_execution",
                rationale="Executing goal based on input context",
                chosen_action="Returned conversational response to user",
                confidence=0.9,
            )
            return response_text
        except Exception as e:
            logger.error("Failed to process message: %s", e, exc_info=True)
            self.tracer.record(
                agent=self.__class__.__name__,
                decision_type="task_execution",
                rationale="Executing goal based on input context",
                chosen_action=f"Failed to process message: {e!s}",
                confidence=0.9,
            )
            return f"❌ Error processing your message: {e!s}"

    def _create_task_spec(self, user_message: str) -> dict[str, Any]:
        """
        Convert user message into a ContextBuilder task specification.

        This uses simple heuristics for now. Future: use local LLM for
        semantic understanding and smart scope detection.

        Args:
            user_message: Raw user input

        Returns:
            Task spec for ContextBuilder
        """
        return _create_task_spec(user_message, self._extract_keywords)

    def _extract_keywords(self, message: str) -> list[str]:
        """
        Extract potential symbol names or file paths from user message.

        Simple implementation for Phase 1. Future: use local LLM embeddings
        for semantic similarity search.

        Args:
            message: User's natural language message

        Returns:
            List of keywords/symbols to search for
        """
        return _extract_keywords(message)

    def _build_llm_prompt(
        self, user_message: str, context_package: dict[str, Any]
    ) -> str:
        """
        Build the prompt to send to the LLM.

        Includes:
        - System context about CORE
        - The extracted context package
        - The user's question
        - Instructions for the LLM

        Args:
            user_message: Original user query
            context_package: Minimal context from ContextBuilder

        Returns:
            Complete prompt for LLM
        """
        return _build_llm_prompt(
            user_message, context_package, self._format_context_items
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
