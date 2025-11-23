# tests/unit/test_config.py

import pytest

from shared.config import Settings


def test_settings_loads_defined_attributes(monkeypatch):
    """Test that explicitly defined attributes are loaded correctly."""

    # 1. Temporarily disable the load_dotenv function so it does nothing.
    #    This prevents the __init__ method from overwriting our test environment.
    monkeypatch.setattr("shared.config.load_dotenv", lambda *args, **kwargs: None)

    # 2. Set the environment variable we want to test.
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    # 3. Now, create the Settings instance. Its __init__ will run, but the
    #    load_dotenv calls inside it will be neutralized by our patch.
    settings = Settings()

    # 4. The assertion will now pass, because only monkeypatch has set the value.
    assert settings.LOG_LEVEL == "DEBUG"


def test_settings_loads_extra_vars_via_constructor():
    """
    Tests that extra variables passed to the constructor are handled correctly
    in Pydantic v2 with extra='allow'.
    """
    # Arrange: Create a settings instance with extra keyword arguments.
    # This is the correct way to test the "extra" fields behavior.
    settings = Settings(
        MY_DYNAMIC_VARIABLE="hello_world",
        CHEAP_API_KEY="cheap_key_123",
        _env_file=None,  # Prevent loading the real .env file for test isolation
    )

    # Assert: In Pydantic v2, extra fields ARE accessible as direct attributes.
    assert hasattr(settings, "MY_DYNAMIC_VARIABLE")
    assert settings.MY_DYNAMIC_VARIABLE == "hello_world"
    assert hasattr(settings, "CHEAP_API_KEY")
    assert settings.CHEAP_API_KEY == "cheap_key_123"

    # Assert: They are ALSO correctly stored in the model_extra dictionary.
    assert "MY_DYNAMIC_VARIABLE" in settings.model_extra
    assert settings.model_extra["MY_DYNAMIC_VARIABLE"] == "hello_world"
    assert "CHEAP_API_KEY" in settings.model_extra
    assert settings.model_extra["CHEAP_API_KEY"] == "cheap_key_123"

    # Assert: They are not confused with the model's formally defined fields.
    defined_fields = set(Settings.model_fields.keys())
    assert "MY_DYNAMIC_VARIABLE" not in defined_fields


def test_settings_accessing_nonexistent_attribute_raises_error():
    """Test that accessing a truly non-existent attribute raises an AttributeError."""
    settings = Settings(_env_file=None)
    with pytest.raises(AttributeError):
        _ = settings.THIS_DOES_NOT_EXIST
