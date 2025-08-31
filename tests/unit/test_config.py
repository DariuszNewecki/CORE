# tests/unit/test_config.py
import os

from shared.config import Settings


def test_settings_loads_defined_attributes(monkeypatch):
    """Test that explicitly defined attributes are loaded correctly."""
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    settings = Settings(_env_file=None)
    assert settings.LOG_LEVEL == "DEBUG"


def test_settings_loads_extra_dynamic_vars():
    """Test that extra variables are loaded dynamically into model_extra."""
    # Set environment variables directly (more reliable than monkeypatch for Pydantic)
    os.environ["MY_DYNAMIC_VARIABLE"] = "hello_world"
    os.environ["CHEAP_API_KEY"] = "cheap_key_123"

    try:
        settings = Settings(_env_file=None)

        # Test direct attribute access (this should work with extra="allow")
        assert hasattr(settings, "MY_DYNAMIC_VARIABLE")
        assert settings.MY_DYNAMIC_VARIABLE == "hello_world"
        assert hasattr(settings, "CHEAP_API_KEY")
        assert settings.CHEAP_API_KEY == "cheap_key_123"

        # Test model_extra access
        assert settings.model_extra.get("MY_DYNAMIC_VARIABLE") == "hello_world"
        assert settings.model_extra.get("CHEAP_API_KEY") == "cheap_key_123"

        # Verify they are actually in the extra fields (not regular fields)
        defined_fields = set(Settings.model_fields.keys())
        assert "MY_DYNAMIC_VARIABLE" not in defined_fields
        assert "CHEAP_API_KEY" not in defined_fields

    finally:
        # Clean up
        os.environ.pop("MY_DYNAMIC_VARIABLE", None)
        os.environ.pop("CHEAP_API_KEY", None)


def test_settings_accessing_nonexistent_attribute_raises_error():
    """Test that accessing a truly non-existent attribute raises an AttributeError."""
    import pytest

    settings = Settings(_env_file=None)
    with pytest.raises(AttributeError):
        _ = settings.THIS_DOES_NOT_EXIST


def test_model_extra_with_constructor_kwargs():
    """Test that we can create settings with extra kwargs and access them through model_extra."""
    # Create settings instance with extra keyword arguments
    settings = Settings(CUSTOM_VAR_1="value1", CUSTOM_VAR_2="value2", _env_file=None)

    # These should be accessible as attributes
    assert settings.CUSTOM_VAR_1 == "value1"
    assert settings.CUSTOM_VAR_2 == "value2"

    # And through model_extra
    assert settings.model_extra.get("CUSTOM_VAR_1") == "value1"
    assert settings.model_extra.get("CUSTOM_VAR_2") == "value2"
