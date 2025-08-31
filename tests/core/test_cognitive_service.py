# tests/core/test_cognitive_service.py
"""
Integration tests for the CognitiveService to ensure it correctly uses the
DeductionAgent to make policy-driven decisions.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from core.cognitive_service import CognitiveService
from shared.config import Settings


@pytest.fixture
def mock_constitution(tmp_path: Path) -> Path:
    intent_dir = tmp_path / ".intent"
    (intent_dir / "policies").mkdir(parents=True)
    (intent_dir / "knowledge").mkdir(parents=True)
    deduction_policy = {
        "scoring_weights": {"cost": 0.8, "speed": 0.2, "quality": 0.0, "reasoning": 0.0}
    }
    (intent_dir / "policies" / "deduction_policy.yaml").write_text(
        yaml.dump(deduction_policy)
    )
    resource_manifest = {
        "llm_resources": [
            {
                "name": "expensive_high_quality_model",
                "env_prefix": "EXPENSIVE",
                "performance_metadata": {"cost_rating": 5, "speed_rating": 1},
            },
            {
                "name": "cheap_fast_model",
                "env_prefix": "CHEAP",
                "performance_metadata": {"cost_rating": 1, "speed_rating": 5},
            },
        ]
    }
    (intent_dir / "knowledge" / "resource_manifest.yaml").write_text(
        yaml.dump(resource_manifest)
    )
    cognitive_roles = {
        "cognitive_roles": [
            {"role": "Proofreader", "assigned_resource": "cheap_fast_model"}
        ]
    }
    (intent_dir / "knowledge" / "cognitive_roles.yaml").write_text(
        yaml.dump(cognitive_roles)
    )
    return tmp_path


def test_cognitive_service_selects_cheapest_model_based_on_policy(
    mock_constitution: Path, monkeypatch
):
    """
    Verify that the CognitiveService, guided by the DeductionAgent, selects the
    resource that best matches the scoring policy (in this case, prioritizing cost).
    """
    # Arrange: Set up dummy environment variables for our test models
    monkeypatch.setenv("CHEAP_API_URL", "http://cheap.api")
    monkeypatch.setenv("CHEAP_API_KEY", "cheap_key")
    monkeypatch.setenv("CHEAP_MODEL_NAME", "cheap-model")
    monkeypatch.setenv("EXPENSIVE_API_URL", "http://expensive.api")
    monkeypatch.setenv("EXPENSIVE_API_KEY", "expensive_key")
    monkeypatch.setenv("EXPENSIVE_MODEL_NAME", "expensive-model")

    # Arrange: Create a temporary settings instance for this test
    # that uses our mock constitution's paths and includes the env vars directly
    test_settings = Settings(
        MIND=mock_constitution / ".intent",
        RESOURCE_MANIFEST_PATH=mock_constitution
        / ".intent/knowledge/resource_manifest.yaml",
        # Pass the environment variables directly to ensure they're loaded
        CHEAP_API_URL="http://cheap.api",
        CHEAP_API_KEY="cheap_key",
        CHEAP_MODEL_NAME="cheap-model",
        EXPENSIVE_API_URL="http://expensive.api",
        EXPENSIVE_API_KEY="expensive_key",
        EXPENSIVE_MODEL_NAME="expensive-model",
        _env_file=None,
    )

    # Import the DeductionAgent here since we need it in the test
    from agents.deduction_agent import DeductionAgent

    # Act: Use dependency injection by patching the 'settings' object that will be
    # imported by the cognitive_service module. Since DeductionAgent receives settings
    # through its constructor, we don't need to patch it separately.
    with patch("core.cognitive_service.settings", test_settings):
        # Create the service and pass the test settings directly to ensure proper initialization
        service = CognitiveService(repo_path=mock_constitution)
        # Override the deduction agent to use our test settings
        service._deduction_agent = DeductionAgent(settings=test_settings)

        client = service.get_client_for_role("Proofreader")

        # Assert
        assert client.model_name == "cheap-model"
        assert "cheap.api" in client.api_url
