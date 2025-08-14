# tests/core/test_intent_model.py

from pathlib import Path

import pytest
from core.intent_model import IntentModel


# Use a more specific fixture to get the project root
@pytest.fixture(scope="module")
def project_root() -> Path:
    """Fixture to provide the absolute path to the project root."""
    # This assumes the tests are run from the project root, which pytest does.
    return Path.cwd().resolve()


@pytest.fixture(scope="module")
def intent_model(project_root: Path) -> IntentModel:
    """Fixture to provide a loaded IntentModel instance."""
    return IntentModel(project_root)


def test_intent_model_loads_structure(intent_model: IntentModel):
    """Verify that the intent model loads the structure data without crashing."""
    assert intent_model.structure is not None
    assert "core" in intent_model.structure
    assert "agents" in intent_model.structure
    assert isinstance(intent_model.structure["core"], dict)


def test_resolve_domain_for_path_core(intent_model: IntentModel, project_root: Path):
    """Test that a path within the 'core' domain resolves correctly."""
    # Create a dummy path that would exist in the core domain
    core_file_path = project_root / "src" / "core" / "main.py"
    domain = intent_model.resolve_domain_for_path(core_file_path)
    assert domain == "core"


def test_resolve_domain_for_path_agents(intent_model: IntentModel, project_root: Path):
    """Test that a path within the 'agents' domain resolves correctly."""
    agents_file_path = project_root / "src" / "agents" / "planner_agent.py"
    domain = intent_model.resolve_domain_for_path(agents_file_path)
    assert domain == "agents"


def test_resolve_domain_for_path_unassigned(
    intent_model: IntentModel, project_root: Path
):
    """Test that a path outside any defined domain resolves to None."""
    # A path that doesn't fall into any defined source structure domain
    other_file_path = project_root / "README.md"
    domain = intent_model.resolve_domain_for_path(other_file_path)
    # The current implementation might resolve to None or a default.
    # Based on the code, it should be None as it's outside 'src'.
    assert domain is None


def test_get_domain_permissions_core(intent_model: IntentModel):
    """Check the permissions for a domain that has defined allowed_imports."""
    core_permissions = intent_model.get_domain_permissions("core")
    assert isinstance(core_permissions, list)
    assert "shared" in core_permissions
    assert "agents" in core_permissions


def test_get_domain_permissions_unrestricted(intent_model: IntentModel):
    """Check that a domain without 'allowed_imports' returns an empty list."""
    # Assuming a domain 'policies' might not have explicit imports defined
    # in source_structure.yaml. This may need adjustment if that file changes.
    policy_permissions = intent_model.get_domain_permissions("policies")
    assert isinstance(policy_permissions, list)
    assert policy_permissions == []
