# src/will/agents/conversational_agent.py
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

from services.context.builder import ContextBuilder
from shared.logger import getLogger
from will.orchestration.cognitive_service import CognitiveService


logger = getLogger(__name__)


# ID: TBD (will be assigned during dev-sync)
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
            >>> print(response)
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
        # Simple keyword extraction for scope hints
        # Future: Use local embedding model for semantic search
        keywords = self._extract_keywords(user_message)

        return {
            "task_id": f"chat-{hash(user_message) & 0xFFFFFFFF:08x}",
            "task_type": "conversational",
            "summary": user_message,
            "privacy": "local_only",
            "scope": {
                "include": keywords,  # ContextBuilder will use these as hints
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
        # Look for capitalized words (likely class names)
        import re

        # CamelCase or words with specific patterns
        keywords = []

        # Find CamelCase (e.g., ContextBuilder, CoreContext)
        camel_case = re.findall(r"\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b", message)
        keywords.extend(camel_case)

        # Find snake_case (e.g., context_builder, build_for_task)
        snake_case = re.findall(r"\b[a-z]+(?:_[a-z]+)+\b", message)
        keywords.extend(snake_case)

        # Find file paths (e.g., src/services/context/builder.py)
        file_paths = re.findall(r"\b(?:src/)?[\w/]+\.py\b", message)
        keywords.extend(file_paths)

        logger.debug(f"Extracted keywords: {keywords}")
        return keywords

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
        # Extract key info from context package
        context_items = context_package.get("context", [])
        num_items = len(context_items)

        # Format context items for the LLM
        formatted_context = self._format_context_items(context_items)

        prompt = f"""You are CORE's conversational assistant, helping a developer understand their codebase.

The developer asked: "{user_message}"

I've extracted {num_items} relevant pieces of context from the codebase:

{formatted_context}

Please provide a clear, concise answer to their question based on this context.

Instructions:
- Focus on answering their specific question
- Use code examples from the context when helpful
- Be conversational and friendly
- If the context doesn't contain enough information, say so
- Keep your response under 500 words

Your response:"""

        return prompt

    # ID: TBD
    def _format_context_items(self, items: list[dict[str, Any]]) -> str:
        """
        Format context items into readable text for LLM.

        Args:
            items: List of context items from ContextPackage

        Returns:
            Formatted string representation
        """
        if not items:
            return "(No specific context found - the question may be too general)"

        formatted = []
        for i, item in enumerate(items, 1):
            name = item.get("name", "Unknown")
            item_type = item.get("item_type", "unknown")
            path = item.get("path", "")
            summary = item.get("summary", "")
            content = item.get("content", "")

            formatted.append(f"--- Context Item {i}: {name} ({item_type}) ---")
            if path:
                formatted.append(f"Location: {path}")
            if summary:
                formatted.append(f"Summary: {summary}")
            if content:
                # Truncate very long content
                if len(content) > 2000:
                    content = content[:2000] + "\n... (truncated)"
                formatted.append(f"Code:\n{content}")
            formatted.append("")  # Blank line between items

        return "\n".join(formatted)


# Factory function for CLI to create agent instance
# ID: TBD
async def create_conversational_agent() -> ConversationalAgent:
    """
    Factory to create a ConversationalAgent with all dependencies wired.

    This is the composition root for the conversational interface.
    Uses CORE's existing service registry and dependency injection patterns.

    Returns:
        Fully initialized ConversationalAgent
    """
    from body.services.service_registry import service_registry
    from services.context.providers import DBProvider, VectorProvider

    # Get or create CognitiveService from registry (singleton pattern)
    cognitive_service = await service_registry.get_cognitive_service()

    # Get Qdrant client if available and wrap it in VectorProvider
    vector_provider = None
    try:
        qdrant_client = await service_registry.get_qdrant_service()
        # VectorProvider wraps QdrantService and provides the interface ContextBuilder expects
        vector_provider = VectorProvider(
            qdrant_client=qdrant_client,
            cognitive_service=cognitive_service,
        )
        logger.info("Vector search enabled via Qdrant")
    except Exception as e:
        logger.warning(f"Qdrant not available: {e}. Context search will be limited")

    # Create DBProvider - it handles sessions internally
    db_provider = DBProvider()

    # Create ContextBuilder with available services
    context_builder = ContextBuilder(
        db_provider=db_provider,
        vector_provider=vector_provider,  # Now properly wrapped
        ast_provider=None,  # Not used in current implementation
        config={},
    )

    # Create and return agent
    agent = ConversationalAgent(
        context_builder=context_builder,
        cognitive_service=cognitive_service,
    )

    logger.info("ConversationalAgent created successfully")
    return agent
