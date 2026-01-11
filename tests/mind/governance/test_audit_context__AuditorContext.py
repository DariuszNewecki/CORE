"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/mind/governance/audit_context.py
- Symbol: AuditorContext
- Status: 8 tests passed, some failed
- Passing tests: test_auditor_context_initialization, test_intent_root_property, test_charter_path_property, test_mind_path_property, test_python_files_cached_property, test_load_knowledge_graph_failure, test_load_governance_resources, test_load_governance_resources_failure
- Generated: 2026-01-11 01:37:31
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mind.governance.audit_context import AuditorContext


def test_auditor_context_initialization():
    """Test basic initialization of AuditorContext."""
    repo_path = Path("/test/repo")
    context = AuditorContext(repo_path)
    assert context.repo_path == repo_path.resolve()
    assert context.last_findings == []
    assert isinstance(context.policies, dict)
    assert isinstance(context.knowledge_graph, dict)
    assert "symbols" in context.knowledge_graph
    assert context.symbols_list == []
    assert context.symbols_map == {}
    mock_settings = MagicMock()
    mock_settings.paths = MagicMock()
    mock_settings.paths.repo_root = Path("/test/repo")
    mock_settings.paths.intent_root = Path("/test/repo/.intent")
    mock_settings.paths.var_dir = Path("/test/repo/var")
    context = AuditorContext(repo_path, mock_settings)
    assert context.paths == mock_settings.paths


def test_intent_root_property():
    """Test the intent_root property."""
    repo_path = Path("/test/repo")
    context = AuditorContext(repo_path)
    mock_paths = MagicMock()
    mock_paths.intent_root = Path("/test/repo/.intent")
    context.paths = mock_paths
    context.intent_path = mock_paths.intent_root
    assert context.intent_root == Path("/test/repo/.intent")


def test_charter_path_property():
    """Test the deprecated charter_path property."""
    repo_path = Path("/test/repo")
    context = AuditorContext(repo_path)
    mock_paths = MagicMock()
    mock_paths.intent_root = Path("/test/repo/.intent")
    context.paths = mock_paths
    context.intent_path = mock_paths.intent_root
    with patch("mind.governance.audit_context.logger") as mock_logger:
        result = context.charter_path
        assert result == Path("/test/repo/.intent")
        mock_logger.warning.assert_called_once()


def test_mind_path_property():
    """Test the mind_path property."""
    repo_path = Path("/test/repo")
    context = AuditorContext(repo_path)
    mock_paths = MagicMock()
    mock_paths.var_dir = Path("/test/repo/var")
    context.paths = mock_paths
    assert context.mind_path == Path("/test/repo/var/mind")


def test_python_files_cached_property():
    """Test the python_files cached property."""
    repo_path = Path("/test/repo")
    context = AuditorContext(repo_path)
    test_py_files = [
        Path("/test/repo/src/main.py"),
        Path("/test/repo/src/utils/helper.py"),
        Path("/test/repo/tests/test_main.py"),
    ]
    with patch.object(context, "get_files") as mock_get_files:
        mock_get_files.return_value = test_py_files
        result1 = context.python_files
        assert result1 == test_py_files
        mock_get_files.assert_called_once_with(include=["src/**/*.py", "tests/**/*.py"])
        result2 = context.python_files
        assert result2 == test_py_files
        assert mock_get_files.call_count == 1


@pytest.mark.asyncio
async def test_load_knowledge_graph_failure():
    """Test knowledge graph loading failure."""
    repo_path = Path("/test/repo")
    context = AuditorContext(repo_path)
    with (
        patch("mind.governance.audit_context.KnowledgeService") as mock_service_class,
        patch("mind.governance.audit_context.logger") as mock_logger,
    ):
        mock_service_class.side_effect = Exception("DB connection failed")
        await context.load_knowledge_graph()
        assert context.knowledge_graph == {"symbols": {}}
        assert context.symbols_map == {}
        assert context.symbols_list == []
        mock_logger.error.assert_called()


def test_load_governance_resources():
    """Test loading governance resources."""
    repo_path = Path("/test/repo")
    context = AuditorContext(repo_path)
    mock_intent_repo = MagicMock()
    mock_policy_ref = MagicMock()
    mock_policy_ref.policy_id = "test-policy-1"
    test_policy_data = {"id": "test-policy-1", "name": "Test Policy", "rules": []}
    with (
        patch("mind.governance.audit_context.get_intent_repository") as mock_get_repo,
        patch("mind.governance.audit_context.logger") as mock_logger,
    ):
        mock_get_repo.return_value = mock_intent_repo
        mock_intent_repo.list_policies.return_value = [mock_policy_ref]
        mock_intent_repo.load_policy.return_value = test_policy_data
        resources = context._load_governance_resources()
        assert "test-policy-1" in resources
        assert resources["test-policy-1"] == test_policy_data
        mock_intent_repo.load_policy.assert_called_once_with("test-policy-1")


def test_load_governance_resources_failure():
    """Test governance resources loading failure."""
    repo_path = Path("/test/repo")
    context = AuditorContext(repo_path)
    with (
        patch("mind.governance.audit_context.get_intent_repository") as mock_get_repo,
        patch("mind.governance.audit_context.logger") as mock_logger,
    ):
        mock_get_repo.side_effect = Exception("Repository not found")
        resources = context._load_governance_resources()
        assert resources == {}
        mock_logger.error.assert_called()
