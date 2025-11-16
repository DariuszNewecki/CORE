import json
from unittest.mock import MagicMock

import pytest
from shared.config import settings

from src.will.agents.intent_translator import IntentTranslator


@pytest.fixture
def mock_cognitive_service(mocker):
    """Mocks the CognitiveService and its client to return a predictable, structured response."""
    mock_client = MagicMock()
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
    # FIX: Use the correct import path
    mock_pipeline = mocker.patch(
        "src.will.orchestration.prompt_pipeline.PromptPipeline"
    )
    mock_pipeline.return_value.process.return_value = "Processed prompt"
    return mock_pipeline.return_value


def test_translator_handles_vague_goal(
    mock_cognitive_service, mock_prompt_pipeline, tmp_path
):
    """
    Tests if the IntentTranslator can take a vague, human goal
    and produce a structured, actionable goal.
    """
    (tmp_path / ".intent" / "prompts").mkdir(parents=True)
    prompt_file = tmp_path / ".intent" / "prompts" / "intent_translator.prompt"
    prompt_file.write_text("User Request: {user_input}")

    settings.MIND = tmp_path / ".intent"

    translator = IntentTranslator(mock_cognitive_service)
    vague_goal = "optimize AI client usage"

    ai_json_response = translator.translate(vague_goal)

    response_lower = ai_json_response.lower()
    assert "did you mean to ask" in response_lower
    assert "basellmclient" in response_lower
    assert "cognitiveservice" in response_lower
