"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/shared/path_resolver.py
- Symbol: PathResolver
- Status: verified_in_sandbox
- Generated: 2026-01-11 00:57:57
- 2026-06-07 (#572 Cat B batch 10):
    * Removed four tests that asserted on attributes/methods that never
      existed on PathResolver: list_prompts (2 tests), quarantine_dir,
      work_dir. The autogen vintage emitted them speculatively; the
      canonical surface is the introspection list at module load
      (audit_findings_path, build_dir, canary_dir, ..., morgue_dir,
      proposals_dir, ..., validate_structure, var_dir, workflows_dir, ...).
    * Updated test_prompt_method to match source's current contract:
      ``prompt(name) -> prompts_dir / name`` with FileNotFoundError if the
      candidate path doesn't exist. No .prompt extension is appended; no
      directory components are stripped; backslashes are not interpreted.
    * Updated test_policy_method_file_not_found assertion to match
      source's current error message format: "Policy '...' not found in
      [...]" rather than the autogen vintage's "Constitutional resource
      '...' not found".
    * Updated test_validate_structure_all_missing to assert on
      governance_config error at errors[-1] (source's required-paths list
      now includes governance config; the autogen vintage's intent_root
      assertion was correct *at the time* but is no longer last).
    * Updated test_validate_structure_all_exist to also create the
      governance_config file so the all-exist case actually passes.
"""

import tempfile
from pathlib import Path

import pytest

from shared.path_resolver import PathResolver


class TestPathResolver:
    """Tests for PathResolver class."""

    def test_init_with_repo_root(self):
        """Test initialization with repo_root parameter."""
        # Create a temporary directory to use as repo root
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            # Test repo_root property
            assert resolver.repo_root == repo_root.resolve()

            # Test intent_root default
            assert resolver.intent_root == repo_root.resolve() / ".intent"

            # Test meta defaults to empty dict
            assert resolver._meta == {}

    def test_init_with_meta(self):
        """Test initialization with meta parameter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            meta = {"key": "value", "version": 1}
            resolver = PathResolver(repo_root=repo_root, meta=meta)

            assert resolver._meta == meta

    def test_from_repo_classmethod(self):
        """Test from_repo class method."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            intent_root = Path(tmpdir) / "custom_intent"
            meta = {"test": "data"}

            resolver = PathResolver.from_repo(
                repo_root=repo_root, intent_root=intent_root, meta=meta
            )

            assert resolver.repo_root == repo_root.resolve()
            assert resolver.intent_root == intent_root
            assert resolver._meta == meta

    def test_from_repo_without_intent_root(self):
        """Test from_repo without intent_root parameter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver.from_repo(repo_root=repo_root)

            assert resolver.repo_root == repo_root.resolve()
            assert resolver.intent_root == repo_root.resolve() / ".intent"

    def test_registry_path(self):
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

            expected = repo_root / "var"
            assert resolver.var_dir == expected

    def test_workflows_dir_property(self):
        """Test workflows_dir property."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            expected = repo_root / "var" / "workflows"
            assert resolver.workflows_dir == expected

    def test_build_dir_property(self):
        """Test build_dir property."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            expected = repo_root / "var" / "build"
            assert resolver.build_dir == expected

    def test_reports_dir_property(self):
        """Test reports_dir property."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            expected = repo_root / "var" / "reports"
            assert resolver.reports_dir == expected

    def test_logs_dir_property(self):
        """Test logs_dir property."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            expected = repo_root / "var" / "logs"
            assert resolver.logs_dir == expected

    def test_exports_dir_property(self):
        """Test exports_dir property."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            expected = repo_root / "var" / "exports"
            assert resolver.exports_dir == expected

    def test_context_dir_property(self):
        """Test context_dir property."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            expected = repo_root / "var" / "context"
            assert resolver.context_dir == expected

    def test_context_cache_dir_property(self):
        """Test context_cache_dir property."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            expected = repo_root / "var" / "cache" / "context"
            assert resolver.context_cache_dir == expected

    def test_context_schema_path_method(self):
        """Test context_schema_path method."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            expected = repo_root / "var" / "context" / "schema.yaml"
            assert resolver.context_schema_path() == expected

    def test_knowledge_dir_property(self):
        """Test knowledge_dir property."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            expected = repo_root / "var" / "mind" / "knowledge"
            assert resolver.knowledge_dir == expected

    def test_mind_export_dir_property(self):
        """Test mind_export_dir property."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            expected = repo_root / "var" / "core" / "mind_export"
            assert resolver.mind_export_dir == expected

    def test_mind_export_method(self):
        """Test mind_export method."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            resource = "test_resource"
            expected = repo_root / "var" / "core" / "mind_export" / "test_resource.yaml"
            assert resolver.mind_export(resource) == expected

    def test_proposals_dir_property(self):
        """Test proposals_dir property."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            expected = repo_root / "var" / "workflows" / "proposals"
            assert resolver.proposals_dir == expected

    def test_pending_writes_dir_property(self):
        """Test pending_writes_dir property."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            expected = repo_root / "var" / "workflows" / "pending_writes"
            assert resolver.pending_writes_dir == expected

    def test_canary_dir_property(self):
        """Test canary_dir property."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            expected = repo_root / "var" / "workflows" / "canary"
            assert resolver.canary_dir == expected

    def test_morgue_dir_property(self):
        """Test morgue_dir property."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            expected = repo_root / "var" / "workflows" / "morgue"
            assert resolver.morgue_dir == expected

    def test_prompts_dir_property(self):
        """Test prompts_dir property."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            expected = repo_root / "var" / "prompts"
            assert resolver.prompts_dir == expected

    def test_prompt_method(self):
        """``prompt(name)`` resolves to ``prompts_dir / name`` when the
        candidate path exists, and raises FileNotFoundError otherwise. No
        ``.prompt`` extension is appended; no directory components are
        stripped; backslashes are passed through as literal characters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            # When the prompt path exists, the method returns it.
            prompt_path = repo_root / "var" / "prompts" / "existing_prompt"
            prompt_path.mkdir(parents=True)
            assert resolver.prompt("existing_prompt") == prompt_path

            # When it doesn't exist, FileNotFoundError is raised.
            with pytest.raises(FileNotFoundError, match="Prompt 'missing'"):
                resolver.prompt("missing")

    def test_validate_structure_all_missing(self):
        """validate_structure surfaces an error per missing required path.
        The autogen vintage asserted ``errors[-1]`` was the intent_root
        message, but source's required-paths list now also includes the
        governance config — that one moves to the tail."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            result = resolver.validate_structure()

            assert not result.ok
            assert len(result.errors) > 0
            assert "Missing required directory: var/" in result.errors[0]
            # Intent root and governance config are both surfaced; the
            # governance config now lands last.
            assert any(
                "Missing constitutional intent root" in e for e in result.errors
            )
            assert "Missing governance config" in result.errors[-1]
            assert "checked_paths" in result.metadata

    def test_validate_structure_all_exist(self):
        """validate_structure passes only when every required path is on
        disk — including the governance_config file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            # Create all required directories
            for prop_name in [
                "var_dir",
                "workflows_dir",
                "canary_dir",
                "proposals_dir",
                "pending_writes_dir",
                "prompts_dir",
                "context_dir",
                "context_cache_dir",
                "knowledge_dir",
                "logs_dir",
                "reports_dir",
                "exports_dir",
                "build_dir",
            ]:
                prop = getattr(resolver, prop_name)
                prop.mkdir(parents=True, exist_ok=True)

            # Create intent root and governance config file
            resolver.intent_root.mkdir(exist_ok=True)
            resolver.governance_config_path.parent.mkdir(parents=True, exist_ok=True)
            resolver.governance_config_path.touch()

            result = resolver.validate_structure()

            assert result.ok
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

            # Create intent structure
            policies_dir = repo_root / ".intent" / "policies"
            policies_dir.mkdir(parents=True)

            # Create a policy file
            policy_file = policies_dir / "test_policy.json"
            policy_file.touch()

            # Test direct match
            result = resolver.policy("test_policy")
            assert result == policy_file.resolve()

            # Test with .json extension
            result = resolver.policy("test_policy.json")
            assert result == policy_file.resolve()

    def test_policy_method_with_path_prefix(self):
        """Test policy method with path prefixes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            # Create intent structure with subdirectory
            policies_dir = repo_root / ".intent" / "policies" / "subdir"
            policies_dir.mkdir(parents=True)

            # Create a policy file in subdirectory
            policy_file = policies_dir / "test_policy.yaml"
            policy_file.touch()

            # Test with .intent/ prefix
            result = resolver.policy(".intent/policies/subdir/test_policy")
            assert result == policy_file.resolve()

            # Test with policies/ prefix
            result = resolver.policy("policies/subdir/test_policy")
            assert result == policy_file.resolve()

    def test_policy_method_recursive_stem_lookup(self):
        """Test policy method with recursive stem lookup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            # Create intent structure with nested directories
            standards_dir = repo_root / ".intent" / "standards" / "level1" / "level2"
            standards_dir.mkdir(parents=True)

            # Create a standards file
            standards_file = standards_dir / "test_standard.yml"
            standards_file.touch()

            # Test stem lookup (should find the file recursively)
            result = resolver.policy("test_standard")
            assert result == standards_file.resolve()

    def test_policy_method_file_not_found(self):
        """Test policy method when file is not found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            # Create intent structure but not the specific file
            policies_dir = repo_root / ".intent" / "policies"
            policies_dir.mkdir(parents=True)

            # Should raise FileNotFoundError
            with pytest.raises(FileNotFoundError) as exc_info:
                resolver.policy("nonexistent_policy")

            # Source raises with format: "Policy '<id>' not found in [...]"
            # (the autogen vintage's "Constitutional resource '<id>' not found"
            # message belongs to an earlier API).
            assert "Policy 'nonexistent_policy' not found" in str(exc_info.value)

    def test_policy_method_with_rules_directory(self):
        """Test policy method searches rules directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            resolver = PathResolver(repo_root=repo_root)

            # Create rules directory
            rules_dir = repo_root / ".intent" / "rules"
            rules_dir.mkdir(parents=True)

            # Create a rules file
            rules_file = rules_dir / "test_rule.json"
            rules_file.touch()

            # Test finding rule
            result = resolver.policy("test_rule")
            assert result == rules_file.resolve()
