"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/mind/governance/audit_context.py
- Symbol: AuditorContext
- Generated: 2026-01-11 01:37:31
- 2026-06-07 (#572 Cat B batch 15):
    * Removed test_charter_path_property and test_python_files_cached_property:
      neither ``charter_path`` nor ``python_files`` exist on the current
      AuditorContext surface — the autogen vintage projected attributes
      that never landed. The current public surface is
      ``intent_root, mind_path, get_files, get_tree, load_knowledge_graph,
      reload_governance, sweep_llm_gate_cache, invalidate_file_cache``.
    * test_auditor_context_initialization rewritten for the current
      constructor signature
      ``AuditorContext(repo_path, intent_repository=None, session_provider=None,
                       llm_client=None, stateless=False)``.
      The autogen vintage passed a second positional ``settings`` arg that
      no longer exists.
    * test_load_governance_resources and _failure: source's
      ``_load_governance_resources`` consults ``self.intent_repo``, which
      is bound during __init__ to ``get_intent_repository()`` if no
      ``intent_repository`` kwarg is supplied. The autogen vintage patched
      ``get_intent_repository`` *after* construction — too late, the
      attribute had already been set. Both tests now inject the mock
      via the constructor's ``intent_repository=`` kwarg.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mind.governance.audit_context import AuditorContext


def test_auditor_context_initialization():
    """Basic initialization with the current constructor signature.
    The autogen vintage attempted a two-positional form
    (``AuditorContext(repo_path, settings)``) for a ``settings`` parameter
    that no longer exists; only ``repo_path`` is positional today, and
    paths are derived from a PathResolver attached in __init__."""
    repo_path = Path("/test/repo")
    context = AuditorContext(repo_path)
    assert context.repo_path == repo_path.resolve()
    assert context.last_findings == []
    assert isinstance(context.policies, dict)
    assert isinstance(context.knowledge_graph, dict)
    assert "symbols" in context.knowledge_graph
    assert context.symbols_list == []
    assert context.symbols_map == {}
    # ``paths`` is a PathResolver derived from repo_path; the autogen
    # vintage's ``mock_settings.paths`` second-arg form never worked.
    assert context.paths.repo_root == repo_path.resolve()


def test_intent_root_property():
    """Test the intent_root property."""
    repo_path = Path("/test/repo")
    context = AuditorContext(repo_path)
    mock_paths = MagicMock()
    mock_paths.intent_root = Path("/test/repo/.intent")
    context.paths = mock_paths
    context.intent_path = mock_paths.intent_root
    assert context.intent_root == Path("/test/repo/.intent")


def test_mind_path_property():
    """Test the mind_path property."""
    repo_path = Path("/test/repo")
    context = AuditorContext(repo_path)
    mock_paths = MagicMock()
    mock_paths.var_dir = Path("/test/repo/var")
    context.paths = mock_paths
    assert context.mind_path == Path("/test/repo/var/mind")


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
    """_load_governance_resources iterates ``self.intent_repo.list_policies()``
    and resolves each via ``self.intent_repo.load_policy(policy_id)``,
    storing the result keyed by ``policy_data['id'] or policy_ref.policy_id``.
    The mock intent_repo is injected via the constructor — patching
    ``get_intent_repository`` after construction would be too late since
    __init__ has already bound ``self.intent_repo``."""
    mock_intent_repo = MagicMock()
    mock_policy_ref = MagicMock()
    mock_policy_ref.policy_id = "test-policy-1"
    test_policy_data = {"id": "test-policy-1", "name": "Test Policy", "rules": []}
    mock_intent_repo.list_policies.return_value = [mock_policy_ref]
    mock_intent_repo.load_policy.return_value = test_policy_data

    # __init__ already calls _load_governance_resources once to populate
    # self.policies (source line 173) — calling it again here is the second
    # invocation, so we assert on call shape rather than count.
    context = AuditorContext(Path("/test/repo"), intent_repository=mock_intent_repo)
    resources = context._load_governance_resources()
    assert "test-policy-1" in resources
    assert resources["test-policy-1"] == test_policy_data
    mock_intent_repo.load_policy.assert_called_with("test-policy-1")


def test_load_governance_resources_failure():
    """When ``list_policies`` raises, the broad except returns an empty
    dict and logs an error."""
    mock_intent_repo = MagicMock()
    mock_intent_repo.list_policies.side_effect = Exception("Repository not found")
    context = AuditorContext(Path("/test/repo"), intent_repository=mock_intent_repo)
    with patch("mind.governance.audit_context.logger") as mock_logger:
        resources = context._load_governance_resources()
        assert resources == {}
        mock_logger.error.assert_called()
