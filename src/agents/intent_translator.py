# src/agents/intent_translator.py
"""
Implements the IntentTranslator agent, responsible for converting natural language user requests into structured, executable goals for the CORE system.
"""

from __future__ import annotations

from core.cognitive_service import CognitiveService
from core.prompt_pipeline import PromptPipeline  # <-- ADD THIS IMPORT
from shared.config import settings
from shared.logger import getLogger

log = getLogger("intent_translator")


# CAPABILITY: agent.intent.translate
class IntentTranslator:
    """An agent that translates natural language into structured goals."""

    # CAPABILITY: agents.intent_translator.initialize
    def __init__(self, cognitive_service: CognitiveService):
        """Initializes the translator with the CognitiveService."""
        self.cognitive_service = cognitive_service
        self.prompt_pipeline = PromptPipeline(settings.REPO_PATH)  # <-- ADD THIS LINE
        self.prompt_path = settings.MIND / "prompts" / "intent_translator.prompt"
        if not self.prompt_path.exists():
            raise FileNotFoundError(
                "Constitutional prompt for IntentTranslator not found."
            )
        self.prompt_template = self.prompt_path.read_text(encoding="utf-8")

    # CAPABILITY: natural_language_understanding
    def translate(self, user_input: str) -> str:
        """
        Takes a user's natural language input and translates it into a
        structured goal for the PlannerAgent.
        """
        log.info(f"Translating user intent: '{user_input}'")
        client = self.cognitive_service.get_client_for_role("IntentTranslator")

        # Use the pipeline to inject context into the prompt
        final_prompt = self.prompt_pipeline.process(
            self.prompt_template.format(user_input=user_input)
        )

        structured_goal = client.make_request(final_prompt, user_id="intent_translator")
        log.info(f"Translated goal: '{structured_goal}'")
        return structured_goal
