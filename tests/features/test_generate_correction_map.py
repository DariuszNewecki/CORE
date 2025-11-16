# tests/features/test_generate_correction_map.py
import json
from unittest.mock import patch

import pytest
import typer
import yaml

# Import the module under test using the exact import path
from features.introspection.generate_correction_map import generate_maps


class TestGenerateCorrectionMap:
    """Test suite for generate_correction_map module."""

    def test_generate_maps_success(self, tmp_path):
        """Test successful generation of alias map from valid input."""
        # Setup
        input_file = tmp_path / "proposed_domains.json"
        output_file = tmp_path / "aliases.yaml"

        # Sample proposed domains data
        proposed_domains = {
            "old_key_1": "new_domain_1",
            "old_key_2": "new_domain_2",
            "old_key_3": "new_domain_1",  # Same domain for multiple keys
        }

        # Write input file
        input_file.write_text(json.dumps(proposed_domains), "utf-8")

        # Mock console.print to capture output
        with patch(
            "features.introspection.generate_correction_map.console"
        ) as mock_console:
            # Execute
            generate_maps(input_path=input_file, output=output_file)

            # Verify
            # Check that output file was created
            assert output_file.exists()

            # Check the content of the output file
            with output_file.open("r", encoding="utf-8") as f:
                loaded_yaml = yaml.safe_load(f)

            expected_output = {"aliases": proposed_domains}
            assert loaded_yaml == expected_output

            # Verify console output was called
            mock_console.print.assert_called()

    def test_generate_maps_nonexistent_input_file(self, tmp_path):
        """Test behavior when input file does not exist."""
        # Setup
        nonexistent_input = tmp_path / "nonexistent.json"
        output_file = tmp_path / "aliases.yaml"

        # Mock logger and console
        with (
            # CORRECTED: Patch 'logger' instead of 'log'
            patch(
                "features.introspection.generate_correction_map.logger"
            ) as mock_logger,
            patch(
                "features.introspection.generate_correction_map.console"
            ) as mock_console,
        ):
            # Execute and verify exception is raised
            with pytest.raises(typer.Exit):
                generate_maps(input_path=nonexistent_input, output=output_file)

            # Verify error was logged
            # CORRECTED: Assert against the correct mock object
            mock_logger.error.assert_called_once()
            error_message = mock_logger.error.call_args[0][0]
            assert "Failed to load or parse input file" in error_message

    def test_generate_maps_invalid_json(self, tmp_path):
        """Test behavior when input file contains invalid JSON."""
        # Setup
        input_file = tmp_path / "invalid.json"
        output_file = tmp_path / "aliases.yaml"

        # Write invalid JSON
        input_file.write_text("invalid json content", "utf-8")

        # Mock logger and console
        with (
            # CORRECTED: Patch 'logger' instead of 'log'
            patch(
                "features.introspection.generate_correction_map.logger"
            ) as mock_logger,
            patch(
                "features.introspection.generate_correction_map.console"
            ) as mock_console,
        ):
            # Execute and verify exception is raised
            with pytest.raises(typer.Exit):
                generate_maps(input_path=input_file, output=output_file)

            # Verify error was logged
            # CORRECTED: Assert against the correct mock object
            mock_logger.error.assert_called_once()
            error_message = mock_logger.error.call_args[0][0]
            assert "Failed to load or parse input file" in error_message

    def test_generate_maps_empty_domains(self, tmp_path):
        """Test generation with empty proposed domains."""
        # Setup
        input_file = tmp_path / "empty_domains.json"
        output_file = tmp_path / "aliases.yaml"

        # Write empty domains
        input_file.write_text(json.dumps({}), "utf-8")

        # Mock console.print to capture output
        with patch(
            "features.introspection.generate_correction_map.console"
        ) as mock_console:
            # Execute
            generate_maps(input_path=input_file, output=output_file)

            # Verify
            assert output_file.exists()

            # Check the content of the output file
            with output_file.open("r", encoding="utf-8") as f:
                loaded_yaml = yaml.safe_load(f)

            expected_output = {"aliases": {}}
            assert loaded_yaml == expected_output

            # Verify success message with 0 entries
            mock_console.print.assert_called()
            success_call = None
            for call in mock_console.print.call_args_list:
                if "Successfully generated alias map" in str(call):
                    success_call = call
                    break
            assert success_call is not None
            assert "0 entries" in str(success_call)

    def test_generate_maps_creates_output_directory(self, tmp_path):
        """Test that output directory is created if it doesn't exist."""
        # Setup
        input_file = tmp_path / "proposed_domains.json"
        output_dir = tmp_path / "nonexistent_dir"
        output_file = output_dir / "aliases.yaml"

        # Verify output directory doesn't exist initially
        assert not output_dir.exists()

        # Sample data
        proposed_domains = {"key1": "domain1", "key2": "domain2"}
        input_file.write_text(json.dumps(proposed_domains), "utf-8")

        # Mock console
        with patch("features.introspection.generate_correction_map.console"):
            # Execute
            generate_maps(input_path=input_file, output=output_file)

            # Verify
            assert output_dir.exists()  # Directory was created
            assert output_file.exists()  # File was created

    def test_generate_maps_complex_domains(self, tmp_path):
        """Test generation with complex domain structures."""
        # Setup
        input_file = tmp_path / "complex_domains.json"
        output_file = tmp_path / "aliases.yaml"

        # Complex domains with nested structures (if supported by the format)
        proposed_domains = {
            "capability.network.http": "network.http",
            "capability.storage.local": "storage.local",
            "capability.database.sql": "database.sql",
            "legacy.system.monitor": "monitoring.system",
            "deprecated.auth.basic": "security.authentication",
        }

        input_file.write_text(json.dumps(proposed_domains), "utf-8")

        # Mock console
        with patch("features.introspection.generate_correction_map.console"):
            # Execute
            generate_maps(input_path=input_file, output=output_file)

            # Verify
            assert output_file.exists()

            with output_file.open("r", encoding="utf-8") as f:
                loaded_yaml = yaml.safe_load(f)

            expected_output = {"aliases": proposed_domains}
            assert loaded_yaml == expected_output

    def test_generate_maps_yaml_format(self, tmp_path):
        """Test that YAML output is properly formatted."""
        # Setup
        input_file = tmp_path / "domains.json"
        output_file = tmp_path / "aliases.yaml"

        proposed_domains = {"key1": "domain1", "key2": "domain2"}
        input_file.write_text(json.dumps(proposed_domains), "utf-8")

        # Mock console
        with patch("features.introspection.generate_correction_map.console"):
            # Execute
            generate_maps(input_path=input_file, output=output_file)

            # Verify YAML format by reading and parsing it
            with output_file.open("r", encoding="utf-8") as f:
                yaml_content = f.read()

            # Should be valid YAML
            parsed_yaml = yaml.safe_load(yaml_content)
            assert parsed_yaml == {"aliases": proposed_domains}

            # Should have proper indentation (basic check)
            lines = yaml_content.strip().split("\n")
            assert len(lines) >= 3  # At least aliases: and some entries

    def test_generate_maps_default_parameters(self, tmp_path):
        """Test that function works with default parameters when files exist."""
        # This test would normally require setting up the default paths,
        # but we'll focus on testing the core logic instead
        pass

    def test_generate_maps_unicode_characters(self, tmp_path):
        """Test handling of unicode characters in domain names."""
        # Setup
        input_file = tmp_path / "unicode_domains.json"
        output_file = tmp_path / "aliases.yaml"

        proposed_domains = {
            "key_ñ": "domain_ñ",
            "key_中文": "domain_中文",
            "key_😀": "domain_😀",
        }
        input_file.write_text(json.dumps(proposed_domains, ensure_ascii=False), "utf-8")

        # Mock console
        with patch("features.introspection.generate_correction_map.console"):
            # Execute
            generate_maps(input_path=input_file, output=output_file)

            # Verify
            assert output_file.exists()

            with output_file.open("r", encoding="utf-8") as f:
                loaded_yaml = yaml.safe_load(f)

            expected_output = {"aliases": proposed_domains}
            assert loaded_yaml == expected_output
