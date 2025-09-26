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
    (intent_dir / "charter" / "policies").mkdir(parents=True)  # Policies are in charter
    (intent_dir / "mind" / "knowledge").mkdir(parents=True)  # Knowledge is in mind

    # --- FIX: Policy is now agent_policy.yaml ---
    agent_policy = {
        "resource_selection": {
            "scoring_weights": {
                "cost": 0.8,
                "speed": 0.2,
                "quality": 0.0,
                "reasoning": 0.0,
            }
        }
    }
    (intent_dir / "charter" / "policies" / "agent_policy.yaml").write_text(
        yaml.dump(agent_policy)
    )

    resource_manifest = {
        "llm_resources": [
            {
                "name": "expensive_high_quality_model",
                "env_prefix": "EXPENSIVE",
                "provided_capabilities": ["natural_language_understanding"],
                "performance_metadata": {
                    "cost_rating": 5,
                    "speed_rating": 1,
                    "quality_rating": 5,
                    "reasoning_rating": 5,
                },
            },
            {
                "name": "cheap_fast_model",
                "env_prefix": "CHEAP",
                "provided_capabilities": ["natural_language_understanding"],
                "performance_metadata": {
                    "cost_rating": 1,
                    "speed_rating": 5,
                    "quality_rating": 2,
                    "reasoning_rating": 2,
                },
            },
        ]
    }
    (intent_dir / "mind" / "knowledge" / "resource_manifest.yaml").write_text(
        yaml.dump(resource_manifest)
    )
    cognitive_roles = {
        "cognitive_roles": [
            {
                "role": "Proofreader",
                "description": "A test role",
                "assigned_resource": "cheap_fast_model",  # This is now just a default
                "required_capabilities": ["natural_language_understanding"],
            }
        ]
    }
    (intent_dir / "mind" / "knowledge" / "cognitive_roles.yaml").write_text(
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
    monkeypatch.setenv("CHEAP_API_URL", "http://cheap.api")
    monkeypatch.setenv("CHEAP_API_KEY", "cheap_key")
    monkeypatch.setenv("CHEAP_MODEL_NAME", "cheap-model")
    monkeypatch.setenv("EXPENSIVE_API_URL", "http://expensive.api")
    monkeypatch.setenv("EXPENSIVE_API_KEY", "expensive_key")
    monkeypatch.setenv("EXPENSIVE_MODEL_NAME", "expensive-model")

    test_settings = Settings(
        REPO_PATH=mock_constitution,
        MIND=mock_constitution / ".intent",
        CHEAP_API_URL="http://cheap.api",
        CHEAP_API_KEY="cheap_key",
        CHEAP_MODEL_NAME="cheap-model",
        EXPENSIVE_API_URL="http://expensive.api",
        EXPENSIVE_API_KEY="expensive_key",
        EXPENSIVE_MODEL_NAME="expensive-model",
        _env_file=None,
    )

    # --- FIX: Update the patch paths ---
    with patch("core.agents.deduction_agent.settings", test_settings), patch(
        "core.cognitive_service.settings", test_settings
    ):
        service = CognitiveService(repo_path=mock_constitution)
        client = service.get_client_for_role("Proofreader")

        assert client.model_name == "cheap-model"
        assert "cheap.api" in client.base_url
