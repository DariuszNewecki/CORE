"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/shared/path_resolver.py
- Symbol: PathResolver
- Status: verified_in_sandbox
- Generated: 2026-01-11 00:14:02
"""

import pytest
from pathlib import Path
import tempfile
import os
from shared.path_resolver import PathResolver


class TestPathResolver:
    """Test PathResolver class - all methods return Path objects."""

    def test_init_with_repo_root(self):
        """Test basic initialization with repo_root."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            assert resolver.repo_root == repo_root.resolve()
            assert resolver.intent_root == repo_root.resolve() / ".intent"
            assert resolver._meta == {}

    def test_init_with_meta(self):
        """Test initialization with metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            meta = {"key": "value"}
            resolver = PathResolver(repo_root=repo_root, meta=meta)

            assert resolver._meta == meta

    def test_from_repo_factory_method(self):
        """Test from_repo class method."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            intent_root = Path(tmpdir) / "custom_intent"
            meta = {"test": "data"}

            resolver = PathResolver.from_repo(
                repo_root=repo_root,
                intent_root=intent_root,
                meta=meta
            )

            assert resolver.repo_root == repo_root.resolve()
            assert resolver.intent_root == intent_root
            assert resolver._meta == meta

    def test_from_repo_without_intent_root(self):
        """Test from_repo without intent_root parameter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver.from_repo(repo_root=repo_root)

            assert resolver.intent_root == repo_root.resolve() / ".intent"

    def test_registry_path_property(self):
        """Test registry_path property."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            expected = resolver.intent_root / "schemas" / "META" / "intent_types.json"
            assert resolver.registry_path == expected

    def test_var_dir_property(self):
        """Test var_dir property."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            assert resolver.var_dir == repo_root.resolve() / "var"

    def test_workflows_dir_property(self):
        """Test workflows_dir property."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            expected = repo_root.resolve() / "var" / "workflows"
            assert resolver.workflows_dir == expected

    def test_build_dir_property(self):
        """Test build_dir property."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            expected = repo_root.resolve() / "var" / "build"
            assert resolver.build_dir == expected

    def test_reports_dir_property(self):
        """Test reports_dir property."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            expected = repo_root.resolve() / "var" / "reports"
            assert resolver.reports_dir == expected

    def test_logs_dir_property(self):
        """Test logs_dir property."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            expected = repo_root.resolve() / "var" / "logs"
            assert resolver.logs_dir == expected

    def test_exports_dir_property(self):
        """Test exports_dir property."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            expected = repo_root.resolve() / "var" / "exports"
            assert resolver.exports_dir == expected

    def test_context_dir_property(self):
        """Test context_dir property."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            expected = repo_root.resolve() / "var" / "context"
            assert resolver.context_dir == expected

    def test_context_cache_dir_property(self):
        """Test context_cache_dir property."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            expected = repo_root.resolve() / "var" / "cache" / "context"
            assert resolver.context_cache_dir == expected

    def test_context_schema_path_method(self):
        """Test context_schema_path method."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            expected = resolver.context_dir / "schema.yaml"
            assert resolver.context_schema_path() == expected

    def test_knowledge_dir_property(self):
        """Test knowledge_dir property."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            expected = repo_root.resolve() / "var" / "mind" / "knowledge"
            assert resolver.knowledge_dir == expected

    def test_mind_export_dir_property(self):
        """Test mind_export_dir property."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            expected = repo_root.resolve() / "var" / "core" / "mind_export"
            assert resolver.mind_export_dir == expected

    def test_mind_export_method(self):
        """Test mind_export method."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            resource = "test_resource"
            expected = resolver.mind_export_dir / f"{resource}.yaml"
            assert resolver.mind_export(resource) == expected

    def test_proposals_dir_property(self):
        """Test proposals_dir property."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            expected = resolver.workflows_dir / "proposals"
            assert resolver.proposals_dir == expected

    def test_pending_writes_dir_property(self):
        """Test pending_writes_dir property."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            expected = resolver.workflows_dir / "pending_writes"
            assert resolver.pending_writes_dir == expected

    def test_canary_dir_property(self):
        """Test canary_dir property."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            expected = resolver.workflows_dir / "canary"
            assert resolver.canary_dir == expected

    def test_morgue_dir_property(self):
        """Test morgue_dir property."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            expected = resolver.workflows_dir / "morgue"
            assert resolver.morgue_dir == expected

    def test_quarantine_dir_property(self):
        """Test quarantine_dir property."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            expected = resolver.workflows_dir / "quarantine"
            assert resolver.quarantine_dir == expected

    def test_prompts_dir_property(self):
        """Test prompts_dir property."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            expected = repo_root.resolve() / "var" / "prompts"
            assert resolver.prompts_dir == expected

    def test_prompt_method(self):
        """Test prompt method with various inputs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            # Test basic name
            name = "test_prompt"
            expected = resolver.prompts_dir / f"{name}.prompt"
            assert resolver.prompt(name) == expected

            # Test with spaces
            name_with_spaces = "  test prompt  "
            expected = resolver.prompts_dir / "test prompt.prompt"
            assert resolver.prompt(name_with_spaces) == expected

            # Test with path separators
            name_with_path = "folder/test\\prompt"
            expected = resolver.prompts_dir / "prompt.prompt"
            assert resolver.prompt(name_with_path) == expected

    def test_list_prompts_method_empty_dir(self):
        """Test list_prompts when prompts directory doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            assert resolver.list_prompts() == []

    def test_list_prompts_method_with_files(self):
        """Test list_prompts with existing prompt files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            # Create prompts directory and files
            prompts_dir = repo_root / "var" / "prompts"
            prompts_dir.mkdir(parents=True)

            # Create some prompt files
            (prompts_dir / "test1.prompt").touch()
            (prompts_dir / "test2.prompt").touch()
            (prompts_dir / "test3.prompt").touch()
            # Add a non-prompt file to ensure filtering
            (prompts_dir / "other.txt").touch()

            result = resolver.list_prompts()
            assert result == ["test1", "test2", "test3"]

    def test_work_dir_property(self):
        """Test work_dir property."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            expected = repo_root.resolve() / "work"
            assert resolver.work_dir == expected

    def test_validate_structure_all_missing(self):
        """Test validate_structure when all directories are missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            result = resolver.validate_structure()

            assert result.ok == False
            assert len(result.errors) > 0
            assert "Missing required directory:" in result.errors[0]
            assert "var/" in result.errors[0]
            assert "checked_paths" in result.metadata

    def test_validate_structure_all_exist(self):
        """Test validate_structure when all directories exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            # Create all required directories
            for prop_name in [
                "var_dir", "workflows_dir", "canary_dir", "proposals_dir",
                "pending_writes_dir", "prompts_dir", "context_dir",
                "context_cache_dir", "knowledge_dir", "logs_dir",
                "reports_dir", "exports_dir", "build_dir"
            ]:
                prop = getattr(resolver, prop_name)
                prop.mkdir(parents=True, exist_ok=True)

            # Create intent root
            resolver.intent_root.mkdir(exist_ok=True)

            result = resolver.validate_structure()

            assert result.ok == True
            assert result.errors == []

    def test_repr_method(self):
        """Test __repr__ method."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            expected = f"PathResolver(root={repo_root.resolve()})"
            assert repr(resolver) == expected

    def test_policy_method_direct_match(self):
        """Test policy method with direct file match."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            # Create directory structure
            policies_dir = resolver.intent_root / "policies"
            policies_dir.mkdir(parents=True)

            # Create a policy file
            policy_file = policies_dir / "test_policy.json"
            policy_file.touch()

            result = resolver.policy("test_policy")
            assert result == policy_file

    def test_policy_method_with_extension(self):
        """Test policy method with file extension in input."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            # Create directory structure
            standards_dir = resolver.intent_root / "standards"
            standards_dir.mkdir(parents=True)

            # Create a standards file
            standard_file = standards_dir / "test_standard.yaml"
            standard_file.touch()

            result = resolver.policy("test_standard.yaml")
            assert result == standard_file

    def test_policy_method_with_path_prefix(self):
        """Test policy method with path prefix in input."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            # Create directory structure
            policies_dir = resolver.intent_root / "policies"
            policies_dir.mkdir(parents=True)

            # Create nested policy file
            nested_dir = policies_dir / "nested"
            nested_dir.mkdir()
            policy_file = nested_dir / "nested_policy.json"
            policy_file.touch()

            # Test with policies/ prefix
            result = resolver.policy("policies/nested/nested_policy")
            assert result == policy_file

            # Test with .intent/ prefix
            result2 = resolver.policy(".intent/policies/nested/nested_policy")
            assert result2 == policy_file

    def test_policy_method_recursive_search(self):
        """Test policy method with recursive stem lookup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            # Create directory structure
            rules_dir = resolver.intent_root / "rules"
            rules_dir.mkdir(parents=True)

            # Create nested rules file
            nested_dir = rules_dir / "deep" / "nested"
            nested_dir.mkdir(parents=True)
            rule_file = nested_dir / "my_rule.yaml"
            rule_file.touch()

            result = resolver.policy("my_rule")
            assert result == rule_file

    def test_policy_method_file_not_found(self):
        """Test policy method when file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            # Create empty policies directory
            policies_dir = resolver.intent_root / "policies"
            policies_dir.mkdir(parents=True)

            with pytest.raises(FileNotFoundError) as exc_info:
                resolver.policy("nonexistent_policy")

            assert "Constitutional resource 'nonexistent_policy' not found" in str(exc_info.value)

    def test_policy_method_prioritizes_shorter_path(self):
        """Test policy method prioritizes shorter path when multiple matches exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            # Create directory structure
            policies_dir = resolver.intent_root / "policies"
            policies_dir.mkdir(parents=True)

            # Create policy at root level
            root_policy = policies_dir / "common.json"
            root_policy.touch()

            # Create same-named policy in nested directory
            nested_dir = policies_dir / "deep" / "nested"
            nested_dir.mkdir(parents=True)
            nested_policy = nested_dir / "common.yaml"
            nested_policy.touch()

            # Should return the shorter path (root level)
            result = resolver.policy("common")
            assert result == root_policy
