# tests/unit/test_intent_translator.py
import json
from unittest.mock import MagicMock

import pytest

from agents.intent_translator import IntentTranslator
from shared.config import settings


@pytest.fixture
def mock_cognitive_service(mocker):
    """Mocks the CognitiveService and its client to return a predictable, structured response."""
    mock_client = MagicMock()

    # This is our new, smarter "script" for the mock AI.
    # It returns the JSON that the real AI is supposed to.
    mock_ai_response = json.dumps(
        {
            "status": "vague",
            "suggestion": "The user's goal is a bit vague. Based on the roadmap, did you mean to ask: 'Refactor the codebase to remove the obsolete BaseLLMClient and use CognitiveService'?",
        }
    )
    mock_client.make_request.return_value = mock_ai_response

    mock_service = MagicMock()
    mock_service.get_client_for_role.return_value = mock_client
    return mock_service


@pytest.fixture
def mock_prompt_pipeline(mocker):
    """Mocks the PromptPipeline to prevent file system access during the unit test."""
    mock_pipeline = mocker.patch("agents.intent_translator.PromptPipeline")
    # Make the process method simply return the template it was given.
    mock_instance = mock_pipeline.return_value
    mock_instance.process.side_effect = lambda prompt: prompt
    return mock_instance


def test_translator_handles_vague_goal(
    mock_cognitive_service, mock_prompt_pipeline, tmp_path
):
    """
    Tests if the IntentTranslator can take a vague, human goal
    and produce a structured, actionable goal.
    """
    # Arrange: We need to create a fake prompt file for the translator to load
    (tmp_path / ".intent" / "prompts").mkdir(parents=True)
    prompt_file = tmp_path / ".intent" / "prompts" / "intent_translator.prompt"
    prompt_file.write_text("User Request: {user_input}")

    # Temporarily tell the settings to look for files in our test directory
    settings.MIND = tmp_path / ".intent"

    translator = IntentTranslator(mock_cognitive_service)
    vague_goal = "optimize AI client usage"

    # Act
    # The IntentTranslator gets a JSON string back from the AI
    # Our real chat command will be responsible for parsing this JSON
    ai_json_response = translator.translate(vague_goal)

    # Assert
    # We assert that the raw JSON string contains the keywords we expect, in lowercase
    response_lower = ai_json_response.lower()
    assert "did you mean to ask" in response_lower
    assert "basellmclient" in response_lower  # <-- THIS IS THE FIX (all lowercase)
    assert "cognitiveservice" in response_lower
