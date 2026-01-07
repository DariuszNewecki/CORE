from unittest.mock import patch

from shared.utils.manifest_aggregator import aggregate_manifests


class TestManifestAggregator:
    """Test suite for manifest_aggregator module"""

    def test_aggregate_manifests_no_directories(self, tmp_path):
        """Test when no manifest directories exist"""
        result = aggregate_manifests(tmp_path)

        assert result["name"] == "CORE"
        assert result["intent"] == "No intent provided."
        assert result["active_agents"] == []
        assert result["required_capabilities"] == []

    def test_aggregate_manifests_with_proposed_manifests(self, tmp_path):
        """Test when proposed_manifests directory exists and has files"""
        proposed_dir = tmp_path / "reports" / "proposed_manifests"
        proposed_dir.mkdir(parents=True)

        # Create test YAML files
        domain1 = proposed_dir / "domain1.yaml"
        domain1.write_text(
            """
name: Test Domain 1
tags:
  - capability1
  - capability2
  - {key: capability3}
"""
        )

        domain2 = proposed_dir / "domain2.yaml"
        domain2.write_text(
            """
name: Test Domain 2
tags:
  - capability4
  - {key: capability5}
"""
        )

        result = aggregate_manifests(tmp_path)

        expected_capabilities = sorted(
            ["capability1", "capability2", "capability3", "capability4", "capability5"]
        )
        assert result["required_capabilities"] == expected_capabilities

    def test_aggregate_manifests_with_live_manifests(self, tmp_path):
        """Test when only live_manifests directory exists"""
        live_dir = tmp_path / ".intent" / "knowledge" / "domains"
        live_dir.mkdir(parents=True)

        domain1 = live_dir / "domain1.yaml"
        domain1.write_text(
            """
name: Live Domain 1
tags:
  - live_capability1
  - {key: live_capability2}
"""
        )

        result = aggregate_manifests(tmp_path)

        expected_capabilities = sorted(["live_capability1", "live_capability2"])
        assert result["required_capabilities"] == expected_capabilities

    def test_aggregate_manifests_with_monolith_manifest(self, tmp_path):
        """Test when monolith project_manifest.yaml exists"""
        monolith_path = tmp_path / ".intent" / "project_manifest.yaml"
        monolith_path.parent.mkdir(parents=True)

        monolith_path.write_text(
            """
name: Test Project
intent: Test intent description
active_agents:
  - agent1
  - agent2
required_capabilities:
  - monolith_capability1
  - monolith_capability2
"""
        )

        result = aggregate_manifests(tmp_path)

        assert result["name"] == "Test Project"
        assert result["intent"] == "Test intent description"
        assert result["active_agents"] == ["agent1", "agent2"]
        assert result["required_capabilities"] == sorted(
            ["monolith_capability1", "monolith_capability2"]
        )

    def test_aggregate_manifests_combines_all_sources(self, tmp_path):
        """Test combining capabilities from all sources"""
        # Setup proposed manifests
        proposed_dir = tmp_path / "reports" / "proposed_manifests"
        proposed_dir.mkdir(parents=True)
        domain1 = proposed_dir / "domain1.yaml"
        domain1.write_text(
            """
tags:
  - proposed_cap1
  - {key: proposed_cap2}
"""
        )

        # Setup monolith manifest
        monolith_path = tmp_path / ".intent" / "project_manifest.yaml"
        monolith_path.parent.mkdir(parents=True)
        monolith_path.write_text(
            """
name: Combined Project
intent: Combined intent
active_agents: ["combined_agent"]
required_capabilities: ["monolith_cap1", "proposed_cap1"]
"""
        )

        result = aggregate_manifests(tmp_path)

        expected_capabilities = sorted(
            ["proposed_cap1", "proposed_cap2", "monolith_cap1"]
        )
        assert result["name"] == "Combined Project"
        assert result["intent"] == "Combined intent"
        assert result["active_agents"] == ["combined_agent"]
        assert result["required_capabilities"] == expected_capabilities

    def test_aggregate_manifests_handles_invalid_yaml(self, tmp_path, caplog):
        """Test handling of invalid YAML files"""
        proposed_dir = tmp_path / "reports" / "proposed_manifests"
        proposed_dir.mkdir(parents=True)

        # Create invalid YAML file
        invalid_yaml = proposed_dir / "invalid.yaml"
        invalid_yaml.write_text("invalid: yaml: content: [")

        # Create valid YAML file
        valid_yaml = proposed_dir / "valid.yaml"
        valid_yaml.write_text(
            """
tags:
  - valid_capability
"""
        )

        result = aggregate_manifests(tmp_path)

        # Should only include capabilities from valid file
        assert result["required_capabilities"] == ["valid_capability"]
        # Should log error for invalid file
        assert "Skipping invalid YAML file" in caplog.text

    def test_aggregate_manifests_empty_proposed_directory(self, tmp_path):
        """Test when proposed_manifests directory exists but is empty"""
        proposed_dir = tmp_path / "reports" / "proposed_manifests"
        proposed_dir.mkdir(parents=True)

        # Also create live manifests to ensure they're used instead
        live_dir = tmp_path / ".intent" / "knowledge" / "domains"
        live_dir.mkdir(parents=True)
        live_yaml = live_dir / "live.yaml"
        live_yaml.write_text(
            """
tags:
  - live_capability
"""
        )

        result = aggregate_manifests(tmp_path)

        # Should use live manifests since proposed directory is empty
        assert result["required_capabilities"] == ["live_capability"]

    def test_aggregate_manifests_duplicate_capabilities(self, tmp_path):
        """Test deduplication of capabilities"""
        proposed_dir = tmp_path / "reports" / "proposed_manifests"
        proposed_dir.mkdir(parents=True)

        domain1 = proposed_dir / "domain1.yaml"
        domain1.write_text(
            """
tags:
  - duplicate_cap
  - {key: duplicate_cap}
  - unique_cap
"""
        )

        domain2 = proposed_dir / "domain2.yaml"
        domain2.write_text(
            """
tags:
  - duplicate_cap
  - {key: unique_cap2}
"""
        )

        result = aggregate_manifests(tmp_path)

        expected_capabilities = sorted(["duplicate_cap", "unique_cap", "unique_cap2"])
        assert result["required_capabilities"] == expected_capabilities
        assert len(result["required_capabilities"]) == 3  # No duplicates

    def test_aggregate_manifests_mixed_capability_formats(self, tmp_path):
        """Test handling of mixed string and dict capability formats"""
        proposed_dir = tmp_path / "reports" / "proposed_manifests"
        proposed_dir.mkdir(parents=True)

        domain_yaml = proposed_dir / "mixed.yaml"
        domain_yaml.write_text(
            """
tags:
  - string_capability
  - {key: dict_capability, description: "A capability with metadata"}
  - another_string
  - {key: another_dict}
"""
        )

        result = aggregate_manifests(tmp_path)

        expected_capabilities = sorted(
            ["string_capability", "dict_capability", "another_string", "another_dict"]
        )
        assert result["required_capabilities"] == expected_capabilities

    def test_aggregate_manifests_no_tags_in_domain(self, tmp_path):
        """Test when domain manifest has no tags section"""
        proposed_dir = tmp_path / "reports" / "proposed_manifests"
        proposed_dir.mkdir(parents=True)

        domain_yaml = proposed_dir / "no_tags.yaml"
        domain_yaml.write_text(
            """
name: Domain without tags
description: This domain has no capabilities
"""
        )

        result = aggregate_manifests(tmp_path)

        # Should not fail and should return empty capabilities list
        assert result["required_capabilities"] == []

    def test_aggregate_manifests_empty_tags_list(self, tmp_path):
        """Test when domain manifest has empty tags list"""
        proposed_dir = tmp_path / "reports" / "proposed_manifests"
        proposed_dir.mkdir(parents=True)

        domain_yaml = proposed_dir / "empty_tags.yaml"
        domain_yaml.write_text(
            """
name: Domain with empty tags
tags: []
"""
        )

        result = aggregate_manifests(tmp_path)

        # Should handle empty list gracefully
        assert result["required_capabilities"] == []

    @patch("shared.utils.manifest_aggregator.logger")
    def test_aggregate_manifests_logging(self, mock_logger, tmp_path):
        """Test that appropriate logging occurs during aggregation"""
        # Setup test data
        proposed_dir = tmp_path / "reports" / "proposed_manifests"
        proposed_dir.mkdir(parents=True)
        domain_yaml = proposed_dir / "test.yaml"
        domain_yaml.write_text(
            """
tags:
  - test_capability
"""
        )

        aggregate_manifests(tmp_path)

        # Verify debug logs were called
        mock_logger.debug.assert_called()
        mock_logger.warning.assert_called_with(
            "   -> ⚠️ Found proposed manifests. Auditor will use these for validation."
        )

    def test_aggregate_manifests_prefers_proposed_over_live(self, tmp_path):
        """Test that proposed manifests take precedence over live manifests"""
        # Setup both directories
        proposed_dir = tmp_path / "reports" / "proposed_manifests"
        proposed_dir.mkdir(parents=True)
        proposed_yaml = proposed_dir / "proposed.yaml"
        proposed_yaml.write_text(
            """
tags:
  - proposed_capability
"""
        )

        live_dir = tmp_path / ".intent" / "knowledge" / "domains"
        live_dir.mkdir(parents=True)
        live_yaml = live_dir / "live.yaml"
        live_yaml.write_text(
            """
tags:
  - live_capability
"""
        )

        result = aggregate_manifests(tmp_path)

        # Should use proposed manifests, not live ones
        assert result["required_capabilities"] == ["proposed_capability"]
        assert "live_capability" not in result["required_capabilities"]
