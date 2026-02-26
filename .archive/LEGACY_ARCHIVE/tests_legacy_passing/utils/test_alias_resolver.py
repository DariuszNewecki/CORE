# tests/shared/utils/test_alias_resolver.py
"""Tests for alias_resolver module."""

from pathlib import Path
from unittest.mock import patch

from shared.utils.alias_resolver import AliasResolver


class TestAliasResolver:
    """Tests for AliasResolver class."""

    def test_loads_aliases_from_valid_file(self, tmp_path):
        """Test loading aliases from a valid YAML file."""
        alias_file = tmp_path / "aliases.yaml"
        alias_file.write_text("aliases:\n  old_name: new_name\n  legacy: modern")

        resolver = AliasResolver(alias_file)

        assert len(resolver.alias_map) == 2
        assert resolver.alias_map["old_name"] == "new_name"
        assert resolver.alias_map["legacy"] == "modern"

    def test_resolves_aliased_key(self, tmp_path):
        """Test resolving a key that has an alias."""
        alias_file = tmp_path / "aliases.yaml"
        alias_file.write_text("aliases:\n  old: new")

        resolver = AliasResolver(alias_file)

        assert resolver.resolve("old") == "new"

    def test_returns_original_key_when_no_alias(self, tmp_path):
        """Test that keys without aliases are returned unchanged."""
        alias_file = tmp_path / "aliases.yaml"
        alias_file.write_text("aliases:\n  mapped: target")

        resolver = AliasResolver(alias_file)

        assert resolver.resolve("unmapped") == "unmapped"

    def test_handles_missing_file_gracefully(self, tmp_path):
        """Test that missing alias file doesn't raise error."""
        nonexistent = tmp_path / "nonexistent.yaml"

        resolver = AliasResolver(nonexistent)

        assert resolver.alias_map == {}
        assert resolver.resolve("anything") == "anything"

    def test_handles_invalid_yaml_gracefully(self, tmp_path):
        """Test that invalid YAML doesn't crash."""
        alias_file = tmp_path / "bad.yaml"
        alias_file.write_text("invalid: yaml: content:")

        resolver = AliasResolver(alias_file)

        assert resolver.alias_map == {}

    def test_handles_yaml_without_aliases_key(self, tmp_path):
        """Test YAML file without 'aliases' key."""
        alias_file = tmp_path / "aliases.yaml"
        alias_file.write_text("other_key: value")

        resolver = AliasResolver(alias_file)

        assert resolver.alias_map == {}

    def test_handles_empty_aliases(self, tmp_path):
        """Test YAML file with empty aliases."""
        alias_file = tmp_path / "aliases.yaml"
        alias_file.write_text("aliases: {}")

        resolver = AliasResolver(alias_file)

        assert resolver.alias_map == {}
        assert resolver.resolve("key") == "key"

    def test_uses_default_path_when_none_provided(self):
        """Test that default path is used when none provided."""
        with patch("shared.config.settings.REPO_PATH", Path("/fake/repo")):
            with patch("pathlib.Path.exists", return_value=False):
                resolver = AliasResolver()

                assert resolver.alias_map == {}

    def test_handles_non_dict_yaml_content(self, tmp_path):
        """Test YAML file containing non-dict content."""
        alias_file = tmp_path / "aliases.yaml"
        alias_file.write_text("- item1\n- item2")

        resolver = AliasResolver(alias_file)

        assert resolver.alias_map == {}

    def test_multiple_resolutions(self, tmp_path):
        """Test multiple alias resolutions."""
        alias_file = tmp_path / "aliases.yaml"
        alias_file.write_text("aliases:\n  a: x\n  b: y\n  c: z")

        resolver = AliasResolver(alias_file)

        assert resolver.resolve("a") == "x"
        assert resolver.resolve("b") == "y"
        assert resolver.resolve("c") == "z"
        assert resolver.resolve("d") == "d"
