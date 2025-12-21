# tests/shared/test_config.py

import json
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from shared.config import REPO_ROOT, Settings, get_path_or_none


class TestSettings:
    """Test cases for Settings class."""

    def test_settings_initialization_defaults(self):
        """Test Settings initialization with default values."""
        with patch("shared.config.load_dotenv") as mock_load_dotenv:
            with patch.object(Settings, "_load_meta_config") as mock_load_meta:
                # Provide minimal required environment to satisfy Pydantic validation
                with patch.dict(
                    "os.environ", {"REPO_PATH": str(REPO_ROOT)}, clear=False
                ):
                    settings = Settings()

                    # Just verify the settings object was created successfully
                    assert settings.REPO_PATH == REPO_ROOT
                    assert settings.MIND == REPO_ROOT / ".intent"
                    assert settings.BODY == REPO_ROOT / "src"

                    mock_load_dotenv.assert_called()
                    mock_load_meta.assert_called_once()

    def test_settings_initialization_with_core_env(self):
        """Test Settings initialization with specific CORE_ENV."""
        with patch("shared.config.load_dotenv") as mock_load_dotenv:
            with patch.object(Settings, "_load_meta_config") as mock_load_meta:
                settings = Settings(CORE_ENV="TEST")

                assert settings.CORE_ENV == "TEST"
                mock_load_dotenv.assert_called()
                mock_load_meta.assert_called_once()

    def test_get_env_file_name(self):
        """Test _get_env_file_name method with different environments."""
        settings = Settings.__new__(Settings)

        assert settings._get_env_file_name("TEST") == ".env.test"
        assert settings._get_env_file_name("PROD") == ".env.prod"
        assert settings._get_env_file_name("PRODUCTION") == ".env.prod"
        assert settings._get_env_file_name("DEV") == ".env"
        assert settings._get_env_file_name("DEVELOPMENT") == ".env"
        assert settings._get_env_file_name("UNKNOWN") == ".env"

    def test_initialize_for_test(self, tmp_path):
        """Test initialize_for_test method."""
        with patch("shared.config.load_dotenv"):
            with patch.object(Settings, "_load_meta_config") as mock_load_meta:
                settings = Settings()
                test_repo_path = tmp_path / "test_repo"
                test_repo_path.mkdir()

                # Reset the mock call count before calling initialize_for_test
                mock_load_meta.reset_mock()

                settings.initialize_for_test(test_repo_path)

                assert settings.REPO_PATH == test_repo_path
                assert settings.MIND == test_repo_path / ".intent"
                assert settings.BODY == test_repo_path / "src"
                mock_load_meta.assert_called_once()

    def test_load_file_content_yaml(self, tmp_path):
        """Test _load_file_content with YAML file."""
        settings = Settings.__new__(Settings)
        yaml_file = tmp_path / "test.yaml"
        yaml_content = {"key": "value", "nested": {"subkey": "subvalue"}}
        yaml_file.write_text(yaml.dump(yaml_content))

        result = settings._load_file_content(yaml_file)

        assert result == yaml_content

    def test_load_file_content_json(self, tmp_path):
        """Test _load_file_content with JSON file."""
        settings = Settings.__new__(Settings)
        json_file = tmp_path / "test.json"
        json_content = {"key": "value", "nested": {"subkey": "subvalue"}}
        json_file.write_text(json.dumps(json_content))

        result = settings._load_file_content(json_file)

        assert result == json_content

    def test_load_file_content_unsupported_format(self, tmp_path):
        """Test _load_file_content with unsupported file format."""
        settings = Settings.__new__(Settings)
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("some content")

        with pytest.raises(ValueError, match="Unsupported config file type"):
            settings._load_file_content(txt_file)

    def test_load_file_content_empty_yaml(self, tmp_path):
        """Test _load_file_content with empty YAML file."""
        settings = Settings.__new__(Settings)
        yaml_file = tmp_path / "empty.yaml"
        yaml_file.write_text("")

        result = settings._load_file_content(yaml_file)

        assert result == {}

    def test_load_file_content_empty_json(self, tmp_path):
        """Test _load_file_content with empty JSON file."""
        settings = Settings.__new__(Settings)
        json_file = tmp_path / "empty.json"
        json_file.write_text("")

        with pytest.raises(json.decoder.JSONDecodeError):
            settings._load_file_content(json_file)

    def test_get_path_success(self):
        """Test get_path method with valid logical path."""
        with patch("shared.config.load_dotenv"):
            settings = Settings()
            settings._meta_config = {
                "charter": {"main": "charter/main.yaml"},
                "mind": {"config": "mind/config.yaml"},
            }

            result = settings.get_path("charter.main")

            assert result == REPO_ROOT / ".intent" / "charter/main.yaml"

    def test_get_path_with_regular_path(self):
        """Test get_path method with regular (non-charter/mind) path."""
        with patch("shared.config.load_dotenv"):
            settings = Settings()
            settings._meta_config = {"src": {"main": "src/main.py"}}

            result = settings.get_path("src.main")

            assert result == REPO_ROOT / "src/main.py"

    def test_get_path_key_error(self):
        """Test get_path method with non-existent logical path."""
        with patch("shared.config.load_dotenv"):
            settings = Settings()
            settings._meta_config = {"existing": {"key": "path"}}

            with pytest.raises(
                FileNotFoundError, match="Logical path 'nonexistent.path' not found"
            ):
                settings.get_path("nonexistent.path")

    def test_get_path_type_error(self):
        """Test get_path method with invalid path type."""
        with patch("shared.config.load_dotenv"):
            settings = Settings()
            settings._meta_config = {"invalid": {"path": 123}}

            with pytest.raises(
                FileNotFoundError, match="Logical path 'invalid.path' not found"
            ):
                settings.get_path("invalid.path")

    def test_find_logical_path_for_file_success(self):
        """Test find_logical_path_for_file with existing filename."""
        with patch("shared.config.load_dotenv"):
            settings = Settings()
            settings._meta_config = {
                "charter": {"main": "charter/main.yaml"},
                "mind": {"config": "mind/config.yaml"},
            }

            result = settings.find_logical_path_for_file("main.yaml")

            assert result == "charter/main.yaml"

    def test_find_logical_path_for_file_not_found(self):
        """Test find_logical_path_for_file with non-existent filename."""
        with patch("shared.config.load_dotenv"):
            settings = Settings()
            settings._meta_config = {"charter": {"main": "charter/main.yaml"}}

            with pytest.raises(
                ValueError, match="Filename 'nonexistent.yaml' not found"
            ):
                settings.find_logical_path_for_file("nonexistent.yaml")

    def test_find_logical_path_for_file_empty_config(self):
        """Test find_logical_path_for_file with empty meta config."""
        with patch("shared.config.load_dotenv"):
            settings = Settings()
            settings._meta_config = {}

            with pytest.raises(ValueError, match="Filename 'test.yaml' not found"):
                settings.find_logical_path_for_file("test.yaml")

    def test_load_success(self, tmp_path):
        """Test load method with valid logical path."""
        with patch("shared.config.load_dotenv"):
            settings = Settings()
            test_content = {"key": "value", "nested": {"sub": "value"}}

            with patch.object(settings, "get_path") as mock_get_path:
                with patch.object(settings, "_load_file_content") as mock_load_content:
                    mock_get_path.return_value = tmp_path / "test.yaml"
                    mock_load_content.return_value = test_content

                    result = settings.load("charter.main")

                    mock_get_path.assert_called_once_with("charter.main")
                    mock_load_content.assert_called_once_with(
                        mock_get_path.return_value
                    )
                    assert result == test_content

    def test_load_file_not_found(self):
        """Test load method with non-existent file path."""
        with patch("shared.config.load_dotenv"):
            settings = Settings()

            with patch.object(settings, "get_path") as mock_get_path:
                mock_get_path.side_effect = FileNotFoundError("File not found")

                with pytest.raises(FileNotFoundError, match="File not found"):
                    settings.load("nonexistent.path")

    def test_load_parse_error(self):
        """Test load method with file parsing error."""
        with patch("shared.config.load_dotenv"):
            settings = Settings()

            with patch.object(settings, "get_path") as mock_get_path:
                with patch.object(settings, "_load_file_content") as mock_load_content:
                    mock_get_path.return_value = Path("test.yaml")
                    mock_load_content.side_effect = ValueError("Parse error")

                    with pytest.raises(
                        OSError,
                        match=re.escape(
                            "Failed to load or parse file for 'charter.main'"
                        ),
                    ):
                        settings.load("charter.main")

    def test_load_meta_config_file_exists(self, tmp_path):
        """Test _load_meta_config when meta.yaml exists."""
        with patch("shared.config.load_dotenv"):
            settings = Settings()
            settings.REPO_PATH = tmp_path

            meta_dir = tmp_path / ".intent"
            meta_dir.mkdir()
            meta_file = meta_dir / "meta.yaml"
            meta_content = {"charter": {"main": "charter/main.yaml"}}
            meta_file.write_text(yaml.dump(meta_content))

            settings._load_meta_config()

            assert settings._meta_config == meta_content

    def test_load_meta_config_file_not_exists(self, tmp_path):
        """Test _load_meta_config when meta.yaml doesn't exist."""
        with patch("shared.config.load_dotenv"):
            settings = Settings()
            settings.REPO_PATH = tmp_path

            settings._load_meta_config()

            assert settings._meta_config == {}

    def test_load_meta_config_parse_error(self, tmp_path):
        """Test _load_meta_config with invalid YAML content."""
        with patch("shared.config.load_dotenv"):
            settings = Settings()
            settings.REPO_PATH = tmp_path

            meta_dir = tmp_path / ".intent"
            meta_dir.mkdir()
            meta_file = meta_dir / "meta.yaml"
            # Write truly invalid YAML - tabs instead of spaces in mapping
            meta_file.write_text("key:\n\tvalue")

            # The error could be either RuntimeError (wrapped) or yaml.scanner.ScannerError (direct)
            with pytest.raises((RuntimeError, yaml.scanner.ScannerError)):
                settings._load_meta_config()


class TestGetPathOrNone:
    """Test cases for get_path_or_none function."""

    def test_get_path_or_none_success(self):
        """Test get_path_or_none with valid logical path."""
        mock_settings = MagicMock()
        mock_settings.get_path.return_value = Path("/test/path")

        with patch("shared.config.settings", mock_settings):
            result = get_path_or_none("charter.main")

            assert result == Path("/test/path")
            mock_settings.get_path.assert_called_once_with("charter.main")

    def test_get_path_or_none_exception(self):
        """Test get_path_or_none when get_path raises exception."""
        mock_settings = MagicMock()
        mock_settings.get_path.side_effect = FileNotFoundError("Not found")

        with patch("shared.config.settings", mock_settings):
            result = get_path_or_none("invalid.path")

            assert result is None

    def test_get_path_or_none_no_settings(self):
        """Test get_path_or_none when settings is not available."""
        with patch("shared.config.settings", None):
            result = get_path_or_none("any.path")

            assert result is None

    def test_get_path_or_none_settings_not_in_globals(self):
        """Test get_path_or_none when settings is not in globals."""
        with patch("shared.config.settings", None):
            # Simulate the case where 'settings' is not in globals
            with patch("shared.config.__builtins__", {"globals": lambda: {}}):
                result = get_path_or_none("any.path")

                assert result is None


class TestSettingsEnvFileLoading:
    """Test environment file loading behavior."""

    def test_env_file_loading_with_existing_file(self, tmp_path):
        """Test environment file loading when file exists."""
        with patch("shared.config.REPO_ROOT", tmp_path):
            env_file = tmp_path / ".env.test"
            env_file.write_text("TEST_VAR=test_value")

            with patch("shared.config.load_dotenv") as mock_load_dotenv:
                with patch.object(Settings, "_load_meta_config"):
                    Settings(CORE_ENV="TEST")

                    # Should be called twice: once for .env and once for .env.test
                    assert mock_load_dotenv.call_count == 2
                    # Verify the test env file was loaded
                    mock_load_dotenv.assert_any_call(env_file, override=True)

    def test_env_file_loading_with_missing_file(self, tmp_path):
        """Test environment file loading when file doesn't exist."""
        with patch("shared.config.REPO_ROOT", tmp_path):
            with patch("shared.config.load_dotenv") as mock_load_dotenv:
                with patch.object(Settings, "_load_meta_config"):
                    with patch("shared.config.logger") as mock_logger:
                        Settings(CORE_ENV="TEST")

                        # Should still be called for .env even if .env.test doesn't exist
                        mock_load_dotenv.assert_called()
                        mock_logger.warning.assert_called_once()
