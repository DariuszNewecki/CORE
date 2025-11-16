# src/will/agents/intent_translator.py

"""
Implements the IntentTranslator agent,
responsible for converting natural language user requests into structured,
executable goals for the CORE system.
"""

from __future__ import annotations

from shared.config import settings
from shared.logger import getLogger

from will.orchestration.cognitive_service import CognitiveService
from will.orchestration.prompt_pipeline import PromptPipeline

logger = getLogger(__name__)


# ID: c9b4aa40-7823-4722-b6be-979d1eb5f1b5
class IntentTranslator:
    """An agent that translates natural language into structured goals."""

    def __init__(self, cognitive_service: CognitiveService):
        """Initializes the translator with the CognitiveService."""
        self.cognitive_service = cognitive_service
        self.prompt_pipeline = PromptPipeline(settings.REPO_PATH)
        self.prompt_path = settings.MIND / "prompts" / "intent_translator.prompt"
        if not self.prompt_path.exists():
            raise FileNotFoundError(
                "Constitutional prompt for IntentTranslator not found."
            )
        self.prompt_template = self.prompt_path.read_text(encoding="utf-8")

    # ID: 5d47894a-2952-4783-afc1-6b05cc46ad13
    def translate(self, user_input: str) -> str:
        """
        Takes a user's natural language input and translates it into a
        structured goal for the PlannerAgent.
        """
        logger.info(f"Translating user intent: '{user_input}'")
        client = self.cognitive_service.get_client_for_role("IntentTranslator")
        final_prompt = self.prompt_pipeline.process(
            self.prompt_template.format(user_input=user_input)
        )
        structured_goal = client.make_request(final_prompt, user_id="intent_translator")
        logger.info(f"Translated goal: '{structured_goal}'")
        return structured_goal
