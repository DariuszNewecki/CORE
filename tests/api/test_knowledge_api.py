# tests/api/test_knowledge_api.py
"""
Tests for the /knowledge API endpoints.
"""
import json
from pathlib import Path

from fastapi.testclient import TestClient

from core.main import app

# This client will now be available after installing pytest-fastapi
client = TestClient(app)


def test_list_capabilities_endpoint(tmp_path: Path, monkeypatch):
    """
    Tests the GET /knowledge/capabilities endpoint to ensure it correctly
    reads and returns capabilities from a mock knowledge graph.
    """
    # 1. Arrange: Create a temporary ".intent" structure and a fake knowledge graph.
    intent_dir = tmp_path / ".intent"
    knowledge_dir = intent_dir / "knowledge"
    knowledge_dir.mkdir(parents=True)
    knowledge_graph_path = knowledge_dir / "knowledge_graph.json"

    mock_graph_data = {
        "symbols": {
            "symbol_one": {"capability": "system.test.alpha"},
            "symbol_two": {"capability": "system.test.beta"},
            "symbol_three": {"capability": "unassigned"},  # Should be ignored
            "symbol_four": {
                "capability": "system.test.alpha"
            },  # Duplicates should be handled
        }
    }
    knowledge_graph_path.write_text(json.dumps(mock_graph_data))

    # 2. Arrange: Monkeypatch the application to use our temporary directory as the root.
    # We need to tell the app to look for the .intent dir in our temp folder.
    monkeypatch.chdir(tmp_path)

    # We need to manually reload the service in the app's state since it's
    # initialized at startup. For a test, this is the simplest way.
    from core.knowledge_service import KnowledgeService

    app.state.knowledge_service = KnowledgeService(repo_path=tmp_path)

    # 3. Act: Make a request to the new endpoint.
    response = client.get("/knowledge/capabilities")

    # 4. Assert: Check the response.
    assert response.status_code == 200
    response_data = response.json()

    # The response should contain a list of unique, sorted capabilities.
    expected_capabilities = ["system.test.alpha", "system.test.beta"]
    assert "capabilities" in response_data
    assert response_data["capabilities"] == expected_capabilities
