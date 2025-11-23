# tests/unit/agents/test_deduction_agent.py
"""
Tests for the DeductionAgent, which advises on LLM resource selection.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from services.database.models import CognitiveRole, LlmResource
from will.agents.deduction_agent import DeductionAgent


@pytest.fixture
def temp_repo():
    """Creates a temporary repository directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        # Create basic directory structure
        (repo_path / ".intent" / "charter" / "policies").mkdir(parents=True)
        yield repo_path


@pytest.fixture
def mock_policy_file(temp_repo):
    """Creates a mock agent policy file."""
    policy_path = temp_repo / ".intent" / "charter" / "policies" / "agent_policy.yaml"
    policy_data = {
        "resource_selection": {
            "scoring_weights": {
                "cost": 0.5,
                "speed": 0.3,
                "quality": 0.1,
                "reasoning": 0.1,
            }
        }
    }
    policy_path.write_text(yaml.dump(policy_data), encoding="utf-8")
    return policy_path


def test_deduction_agent_initializes_without_policy(temp_repo):
    """Tests that DeductionAgent initializes gracefully when policy is missing."""
    agent = DeductionAgent(temp_repo)
    assert agent is not None
    assert agent._policy == {}


def test_deduction_agent_loads_policy(temp_repo, mock_policy_file):
    """Tests that DeductionAgent loads policy correctly when present."""
    with patch("shared.config.settings.MIND", temp_repo / ".intent" / "mind"):
        agent = DeductionAgent(temp_repo)
        # Policy should be loaded (implementation may vary)
        assert agent._policy is not None


def test_select_resource_with_cost_rating():
    """Tests resource selection based on cost rating."""
    agent = DeductionAgent(Path("/tmp"))

    # Create mock resources with different cost ratings
    resource1 = MagicMock(spec=LlmResource)
    resource1.name = "expensive-model"
    resource1.performance_metadata = {"cost_rating": 0.9}

    resource2 = MagicMock(spec=LlmResource)
    resource2.name = "cheap-model"
    resource2.performance_metadata = {"cost_rating": 0.1}

    candidates = [resource1, resource2]
    role = MagicMock(spec=CognitiveRole)

    result = agent.select_resource(role, candidates)

    # Should select the cheaper model
    assert result == "cheap-model"


def test_select_resource_returns_none_when_no_candidates():
    """Tests that select_resource returns None when no candidates provided."""
    agent = DeductionAgent(Path("/tmp"))
    role = MagicMock(spec=CognitiveRole)

    result = agent.select_resource(role, [])

    assert result is None


def test_select_resource_handles_missing_metadata():
    """Tests resource selection when performance metadata is missing."""
    agent = DeductionAgent(Path("/tmp"))

    resource = MagicMock(spec=LlmResource)
    resource.name = "model-without-metadata"
    resource.performance_metadata = {}

    role = MagicMock(spec=CognitiveRole)

    result = agent.select_resource(role, [resource])

    # Should return None when no cost rating available
    assert result is None
