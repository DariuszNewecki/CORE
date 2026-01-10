"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/shared/config.py
- Symbol: Settings
- Status: 7 tests passed, some failed
- Passing tests: test_get_env_file_name, test_initialize_for_test, test_paths_property_lazy_initialization, test_get_path_shim, test_settings_extra_fields_allowed, test_settings_path_attributes_are_paths, test_settings_model_config
- Generated: 2026-01-11 00:12:18
"""

import pytest
from pathlib import Path
import tempfile
import os
from shared.config import Settings

def test_get_env_file_name():
    """Test the _get_env_file_name method mapping."""
    settings = Settings(DATABASE_URL='sqlite:///test.db', QDRANT_URL='http://localhost:6333')
    assert settings._get_env_file_name('TEST') == '.env.test'
    assert settings._get_env_file_name('PROD') == '.env.prod'
    assert settings._get_env_file_name('PRODUCTION') == '.env.prod'
    assert settings._get_env_file_name('DEV') == '.env'
    assert settings._get_env_file_name('DEVELOPMENT') == '.env'
    assert settings._get_env_file_name('test') == '.env.test'
    assert settings._get_env_file_name('Prod') == '.env.prod'
    assert settings._get_env_file_name('STAGING') == '.env'
    assert settings._get_env_file_name('') == '.env'

def test_initialize_for_test():
    """Test the initialize_for_test method re-roots paths."""
    settings = Settings(DATABASE_URL='sqlite:///test.db', QDRANT_URL='http://localhost:6333')
    with tempfile.TemporaryDirectory() as tmpdir:
        test_repo_path = Path(tmpdir)
        original_repo_path = settings.REPO_PATH
        original_mind = settings.MIND
        original_body = settings.BODY
        settings.initialize_for_test(test_repo_path)
        assert settings.REPO_PATH == test_repo_path
        assert settings.MIND == test_repo_path / '.intent'
        assert settings.BODY == test_repo_path / 'src'
        assert settings.REPO_PATH != original_repo_path
        assert settings.MIND != original_mind
        assert settings.BODY != original_body
        assert settings._path_resolver == None

def test_paths_property_lazy_initialization():
    """Test that paths property lazily initializes PathResolver."""
    settings = Settings(DATABASE_URL='sqlite:///test.db', QDRANT_URL='http://localhost:6333')
    assert settings._path_resolver == None
    paths = settings.paths
    assert settings._path_resolver is not None
    assert paths == settings._path_resolver
    paths2 = settings.paths
    assert paths2 is paths

def test_get_path_shim():
    """Test the get_path shim method delegates to paths.policy()."""
    settings = Settings(DATABASE_URL='sqlite:///test.db', QDRANT_URL='http://localhost:6333')

    class MockPathResolver:

        def policy(self, logical_path):
            return Path(f'/mock/{logical_path}')
    mock_resolver = MockPathResolver()
    settings._path_resolver = mock_resolver
    result = settings.get_path('test/path')
    assert result == Path('/mock/test/path')

def test_settings_extra_fields_allowed():
    """Test that Settings allows extra fields via extra='allow'."""
    settings = Settings(DATABASE_URL='sqlite:///test.db', QDRANT_URL='http://localhost:6333', EXTRA_FIELD='extra_value', ANOTHER_EXTRA=123)
    assert settings.DATABASE_URL == 'sqlite:///test.db'
    assert settings.QDRANT_URL == 'http://localhost:6333'

def test_settings_path_attributes_are_paths():
    """Test that path attributes are Path objects."""
    settings = Settings(DATABASE_URL='sqlite:///test.db', QDRANT_URL='http://localhost:6333')
    assert isinstance(settings.REPO_PATH, Path)
    assert isinstance(settings.MIND, Path)
    assert isinstance(settings.BODY, Path)
    assert isinstance(settings.KEY_STORAGE_DIR, Path)
    assert isinstance(settings.CORE_ACTION_LOG_PATH, Path)

def test_settings_model_config():
    """Test that model_config is properly set."""
    settings = Settings(DATABASE_URL='sqlite:///test.db', QDRANT_URL='http://localhost:6333')
    assert settings.model_config['env_file'] == None
    assert settings.model_config['env_file_encoding'] == 'utf-8'
    assert settings.model_config['extra'] == 'allow'
    assert settings.model_config['case_sensitive'] == True
