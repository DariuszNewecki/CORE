# tests/unit/test_config.py
from pathlib import Path

from shared.config import Settings


def test_settings_loads_from_env(tmp_path: Path, monkeypatch):
    """Test Settings correctly loads values from environment variables."""
    # Arrange: Set environment variables that the Settings object should pick up
    monkeypatch.setenv("DEEPSEEK_CHAT_API_URL", "https://api.test.com/v1")
    monkeypatch.setenv("DEEPSEEK_CHAT_API_KEY", "test-key")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    # Act: Initialize the Settings object, telling it to ignore the .env file for this test
    settings = Settings(REPO_PATH=tmp_path, _env_file=None)

    # Assert: Check that the settings were loaded correctly from the monkeypatched environment
    assert settings.DEEPSEEK_CHAT_API_URL == "https://api.test.com/v1"
    assert settings.LOG_LEVEL == "DEBUG"


def test_settings_handles_optional_keys(tmp_path: Path, monkeypatch):
    """Test that optional keys default to None if not provided."""
    # Arrange: Ensure a specific optional key is not set in the process environment
    monkeypatch.delenv("ANTHROPIC_CLAUDE_SONNET_API_KEY", raising=False)

    # Act: Initialize the Settings object, telling it to ignore the .env file.
    # This forces it to only see the environment where the key has been removed.
    settings = Settings(REPO_PATH=tmp_path, _env_file=None)  # <-- THIS IS THE FIX

    # Assert: The unset optional key should now correctly be None
    assert settings.ANTHROPIC_CLAUDE_SONNET_API_KEY is None
