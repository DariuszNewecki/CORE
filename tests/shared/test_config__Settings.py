"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/shared/config.py
- Symbol: Settings
- Status: 7 tests passed, some failed
- Passing tests: test_initialize_for_test, test_get_env_file_name, test_paths_property_lazy_initialization, test_get_path_shim, test_load_method_empty_for_nonexistent, test_settings_extra_fields_allowed, test_settings_case_sensitive
- Generated: 2026-01-11 00:56:13
"""

import os
import tempfile
from pathlib import Path

from shared.config import Settings


def test_initialize_for_test():
    """Test the initialize_for_test method re-roots paths correctly."""
    settings = Settings(
        DATABASE_URL="sqlite:///test.db", QDRANT_URL="http://localhost:6333"
    )
    original_repo_path = settings.REPO_PATH
    original_mind = settings.MIND
    original_body = settings.BODY
    with tempfile.TemporaryDirectory() as tmpdir:
        test_repo_path = Path(tmpdir)
        settings.initialize_for_test(test_repo_path)
        assert settings.REPO_PATH == test_repo_path
        assert settings.MIND == test_repo_path / ".intent"
        assert settings.BODY == test_repo_path / "src"
        assert settings._path_resolver is None
        assert settings.REPO_PATH != original_repo_path
        assert settings.MIND != original_mind
        assert settings.BODY != original_body


def test_get_env_file_name():
    """Test the _get_env_file_name method mapping."""
    settings = Settings(
        DATABASE_URL="sqlite:///test.db", QDRANT_URL="http://localhost:6333"
    )
    assert settings._get_env_file_name("TEST") == ".env.test"
    assert settings._get_env_file_name("test") == ".env.test"
    assert settings._get_env_file_name("PROD") == ".env.prod"
    assert settings._get_env_file_name("PRODUCTION") == ".env.prod"
    assert settings._get_env_file_name("DEV") == ".env"
    assert settings._get_env_file_name("DEVELOPMENT") == ".env"
    assert settings._get_env_file_name("unknown") == ".env"
    assert settings._get_env_file_name("") == ".env"


def test_paths_property_lazy_initialization():
    """Test that paths property lazily initializes PathResolver."""
    settings = Settings(
        DATABASE_URL="sqlite:///test.db", QDRANT_URL="http://localhost:6333"
    )
    assert settings._path_resolver is None
    paths = settings.paths
    assert settings._path_resolver is not None
    assert paths == settings._path_resolver
    paths2 = settings.paths
    assert paths2 is paths


def test_get_path_shim():
    """Test the get_path shim method delegates to paths.policy()."""
    settings = Settings(
        DATABASE_URL="sqlite:///test.db", QDRANT_URL="http://localhost:6333"
    )

    class MockPathResolver:

        def policy(self, logical_path):
            return Path(f"/mock/{logical_path}")

    mock_resolver = MockPathResolver()
    settings._path_resolver = mock_resolver
    result = settings.get_path("test/path")
    assert result == Path("/mock/test/path")


def test_load_method_empty_for_nonexistent():
    """Test load method returns empty dict for non-existent files."""
    settings = Settings(
        DATABASE_URL="sqlite:///test.db", QDRANT_URL="http://localhost:6333"
    )

    class MockPathResolver:

        def policy(self, logical_path):
            return Path("/nonexistent/path/file.yaml")

    settings._path_resolver = MockPathResolver()
    result = settings.load("nonexistent")
    assert result == {}


def test_settings_extra_fields_allowed():
    """Test that Settings allows extra fields via extra='allow'."""
    settings = Settings(
        DATABASE_URL="sqlite:///test.db",
        QDRANT_URL="http://localhost:6333",
        EXTRA_FIELD="extra_value",
    )
    assert settings.EXTRA_FIELD == "extra_value"


def test_settings_case_sensitive():
    """Test that Settings is case-sensitive."""
    os.environ["core_env"] = "lowercase"
    settings = Settings(
        DATABASE_URL="sqlite:///test.db", QDRANT_URL="http://localhost:6333"
    )
    assert settings.CORE_ENV == "development"
    del os.environ["core_env"]
