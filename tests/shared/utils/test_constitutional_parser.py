# tests/shared/utils/test_constitutional_parser.py
"""Tests for constitutional_parser module."""

from __future__ import annotations

from shared.utils.constitutional_parser import get_all_constitutional_paths


class TestGetAllConstitutionalPaths:
    """Tests for get_all_constitutional_paths function."""

    def test_finds_paths_in_simple_dict(self, tmp_path):
        """Test finding paths in a simple dictionary."""
        intent_dir = tmp_path / ".intent"
        intent_dir.mkdir()

        meta_content = {
            "policy_file": "charter/policies/safety.yaml",
            "other_file": "prompts/test.prompt",
        }

        paths = get_all_constitutional_paths(meta_content, intent_dir)

        assert ".intent/meta.yaml" in paths
        assert ".intent/charter/policies/safety.yaml" in paths
        assert ".intent/prompts/test.prompt" in paths

    def test_finds_paths_in_nested_dict(self, tmp_path):
        """Test finding paths in nested dictionaries."""
        intent_dir = tmp_path / ".intent"
        intent_dir.mkdir()

        meta_content = {"level1": {"level2": {"file": "deep/nested/file.yaml"}}}

        paths = get_all_constitutional_paths(meta_content, intent_dir)

        assert ".intent/deep/nested/file.yaml" in paths

    def test_finds_paths_in_lists(self, tmp_path):
        """Test finding paths in list values."""
        intent_dir = tmp_path / ".intent"
        intent_dir.mkdir()

        meta_content = {
            "files": ["dir1/file1.yaml", "dir2/file2.yaml", "subdir/file3.yaml"]
        }

        paths = get_all_constitutional_paths(meta_content, intent_dir)

        assert ".intent/dir1/file1.yaml" in paths
        assert ".intent/dir2/file2.yaml" in paths
        assert ".intent/subdir/file3.yaml" in paths

    def test_ignores_strings_without_slashes(self, tmp_path):
        """Test that simple strings without path separators are ignored."""
        intent_dir = tmp_path / ".intent"
        intent_dir.mkdir()

        meta_content = {"name": "test", "version": "1.0", "file": "path/to/file.yaml"}

        paths = get_all_constitutional_paths(meta_content, intent_dir)

        assert ".intent/path/to/file.yaml" in paths
        # Simple strings should not be included
        assert "test" not in paths
        assert "1.0" not in paths

    def test_ignores_strings_containing_intent_dir_name(self, tmp_path):
        """Test that strings already containing .intent are ignored."""
        intent_dir = tmp_path / ".intent"
        intent_dir.mkdir()

        meta_content = {
            "absolute": ".intent/already/absolute/path.yaml",
            "relative": "relative/path.yaml",
        }

        paths = get_all_constitutional_paths(meta_content, intent_dir)

        # Should only have meta.yaml and the relative path
        assert ".intent/meta.yaml" in paths
        assert ".intent/relative/path.yaml" in paths
        # Should not duplicate the absolute path
        assert len([p for p in paths if "already/absolute" in p]) == 0

    def test_handles_empty_dict(self, tmp_path):
        """Test handling empty dictionary."""
        intent_dir = tmp_path / ".intent"
        intent_dir.mkdir()

        paths = get_all_constitutional_paths({}, intent_dir)

        assert ".intent/meta.yaml" in paths
        assert len(paths) == 1

    def test_handles_mixed_content_types(self, tmp_path):
        """Test handling mixed content types."""
        intent_dir = tmp_path / ".intent"
        intent_dir.mkdir()

        meta_content = {
            "string": "dir/file.yaml",
            "number": 42,
            "bool": True,
            "null": None,
            "list": ["list/file.yaml"],
            "dict": {"nested": "nested/file.yaml"},
        }

        paths = get_all_constitutional_paths(meta_content, intent_dir)

        assert ".intent/dir/file.yaml" in paths
        assert ".intent/list/file.yaml" in paths
        assert ".intent/nested/file.yaml" in paths

    def test_handles_windows_style_paths(self, tmp_path):
        """Test handling Windows-style backslash paths."""
        intent_dir = tmp_path / ".intent"
        intent_dir.mkdir()

        meta_content = {"file": "charter\\policies\\safety.yaml"}

        paths = get_all_constitutional_paths(meta_content, intent_dir)

        # Should normalize to forward slashes
        assert any(
            "charter" in p and "policies" in p and "safety.yaml" in p for p in paths
        )

    def test_handles_deeply_nested_structures(self, tmp_path):
        """Test handling deeply nested data structures."""
        intent_dir = tmp_path / ".intent"
        intent_dir.mkdir()

        meta_content = {"a": {"b": {"c": {"d": [{"file": "deep/file.yaml"}]}}}}

        paths = get_all_constitutional_paths(meta_content, intent_dir)

        assert ".intent/deep/file.yaml" in paths

    def test_always_includes_meta_yaml(self, tmp_path):
        """Test that meta.yaml is always included."""
        intent_dir = tmp_path / ".intent"
        intent_dir.mkdir()

        paths = get_all_constitutional_paths({}, intent_dir)

        assert ".intent/meta.yaml" in paths
