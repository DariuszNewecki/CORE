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

from .conversational_agent_helpers import (
    _build_llm_prompt,
    _create_task_spec,
    _extract_keywords,
    _format_context_items,
)


logger = getLogger(__name__)


# ID: TBD (will be assigned during dev-sync)
# ID: c63972c6-5e90-41a8-8f48-1e603617d025
class ConversationalAgent:
    """
    Orchestrates conversational interaction between user and CORE.

    Phase 1: Information retrieval only - helps users understand their codebase
    without making any modifications.
    """

    def __init__(
        self,
        context_builder: ContextBuilder,
        cognitive_service: CognitiveService,
    ):
        """
        Initialize conversational agent.

        Args:
            context_builder: Service to extract minimal context packages
            cognitive_service: Service to communicate with LLM
        """
        self.context_builder = context_builder
        self.cognitive_service = cognitive_service

        logger.info("ConversationalAgent initialized (Phase 1: read-only)")

    # ID: TBD
    # ID: 345f2c69-4453-4181-9d77-5fd1c6dfd6e5
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
        logger.info(f"Processing user message: {user_message[:100]}...")

        try:
            # Step 1: Build a task spec for context extraction
            task_spec = self._create_task_spec(user_message)

            # Step 2: Extract minimal context using ContextBuilder
            logger.info("Extracting context package...")
            context_package = await self.context_builder.build_for_task(task_spec)

            # Step 3: Build prompt for LLM
            prompt = self._build_llm_prompt(user_message, context_package)

            # Step 4: Send to LLM via CognitiveService
            logger.info("Sending to LLM for analysis...")

            # Get an LLM client for conversational tasks
            # Use "Planner" role for now - it's general purpose reasoning
            client = await self.cognitive_service.aget_client_for_role("Planner")

            # Make async request
            llm_response = await client.make_request_async(prompt)

            # Step 5: Return response (Phase 1: no parsing, just pass through)
            return llm_response.strip()

        except Exception as e:
            logger.error(f"Failed to process message: {e}", exc_info=True)
            return f"❌ Error processing your message: {str(e)}"

    # ID: TBD
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

    # ID: TBD
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

    # ID: TBD
    def _build_llm_prompt(
        self,
        user_message: str,
        context_package: dict[str, Any],
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

    # ID: TBD
    def _format_context_items(self, items: list[dict[str, Any]]) -> str:
        """
        Format context items into readable text for LLM.

        Args:
            items: List of context items from ContextPackage

        Returns:
            Formatted string representation
        """
        return _format_context_items(items)
