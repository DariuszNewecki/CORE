# src/will/agents/intent_translator.py

"""
Implements the IntentTranslator agent,
responsible for converting natural language user requests into structured,
executable goals for the CORE system.
"""

from __future__ import annotations

from shared.logger import getLogger
from shared.path_resolver import PathResolver
from will.orchestration.cognitive_service import CognitiveService
from will.orchestration.prompt_pipeline import PromptPipeline


logger = getLogger(__name__)


# ID: c9b4aa40-7823-4722-b6be-979d1eb5f1b5
class IntentTranslator:
    """An agent that translates natural language into structured goals."""

    def __init__(
        self, cognitive_service: CognitiveService, path_resolver: PathResolver
    ):
        """Initializes the translator with the CognitiveService."""
        self.cognitive_service = cognitive_service
        self._paths = path_resolver
        self.prompt_pipeline = PromptPipeline(self._paths.repo_root)

        # ALIGNED: Using PathResolver (var/prompts) instead of .intent
        try:
            self.prompt_template = self._paths.prompt("intent_translator").read_text(
                encoding="utf-8"
            )
        except FileNotFoundError:
            logger.error(
                "Constitutional prompt 'intent_translator.prompt' missing from var/prompts/"
            )
            raise

    # ID: 5d47894a-2952-4783-afc1-6b05cc46ad13
    async def translate(self, user_input: str) -> str:
        """
        Takes a user's natural language input and translates it into a
        structured goal for the PlannerAgent.
        """
        logger.info("Translating user intent: '%s'", user_input)
        client = await self.cognitive_service.aget_client_for_role("IntentTranslator")

        final_prompt = self.prompt_pipeline.process(
            self.prompt_template.format(user_input=user_input)
        )

        structured_goal = await client.make_request_async(
            final_prompt, user_id="intent_translator"
        )
        logger.info("Translated goal: '%s'", structured_goal)
        return structured_goal
