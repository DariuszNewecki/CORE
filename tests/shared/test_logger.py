import logging
from unittest.mock import MagicMock, patch

import pytest
from shared.logger import configure_root_logger, getLogger, reconfigure_log_level


class TestGetLogger:
    """Test getLogger function."""

    def test_get_logger_returns_logger_instance(self):
        """Test that getLogger returns a logging.Logger instance."""
        # Act
        result = getLogger()

        # Assert
        assert isinstance(result, logging.Logger)

    def test_get_logger_with_name_returns_named_logger(self):
        """Test that getLogger with name returns logger with that name."""
        # Arrange
        logger_name = "test_logger"

        # Act
        result = getLogger(logger_name)

        # Assert
        assert result.name == logger_name

    def test_get_logger_default_name(self):
        """Test that getLogger without name uses default logger name."""
        # Act
        result = getLogger()

        # Assert
        assert result.name == "root"


@pytest.mark.skip(reason="Logger implementation changed - needs refactor")
class TestConfigureRootLogger:
    """Test configure_root_logger function."""

    @patch("shared.logger.logging.basicConfig")
    @patch("shared.logger._suppress_noisy_loggers")
    def test_configure_root_logger_default_parameters(
        self, mock_suppress, mock_basic_config
    ):
        """Test configure_root_logger with default parameters."""
        # Act
        configure_root_logger()

        # Assert
        mock_basic_config.assert_called_once()
        mock_suppress.assert_called_once()

    @patch("shared.logger.logging.basicConfig")
    @patch("shared.logger._suppress_noisy_loggers")
    def test_configure_root_logger_custom_level(self, mock_suppress, mock_basic_config):
        """Test configure_root_logger with custom level."""
        # Arrange
        custom_level = "DEBUG"

        # Act
        configure_root_logger(level=custom_level)

        # Assert
        mock_basic_config.assert_called_once()
        call_kwargs = mock_basic_config.call_args[1]
        assert call_kwargs["level"] == logging.DEBUG

    @patch("shared.logger.logging.basicConfig")
    @patch("shared.logger._suppress_noisy_loggers")
    def test_configure_root_logger_custom_format(
        self, mock_suppress, mock_basic_config
    ):
        """Test configure_root_logger with custom format."""
        # Arrange
        custom_format = "%(levelname)s - %(message)s"

        # Act
        configure_root_logger(format_=custom_format)

        # Assert
        mock_basic_config.assert_called_once()
        call_kwargs = mock_basic_config.call_args[1]
        assert call_kwargs["format"] == custom_format

    @patch("shared.logger.logging.basicConfig")
    @patch("shared.logger._suppress_noisy_loggers")
    def test_configure_root_logger_custom_handlers(
        self, mock_suppress, mock_basic_config
    ):
        """Test configure_root_logger with custom handlers."""
        # Arrange
        custom_handlers = [logging.StreamHandler()]

        # Act
        configure_root_logger(handlers=custom_handlers)

        # Assert
        mock_basic_config.assert_called_once()
        call_kwargs = mock_basic_config.call_args[1]
        assert call_kwargs["handlers"] == custom_handlers

    def test_configure_root_logger_invalid_level_raises_value_error(self):
        """Test configure_root_logger with invalid level raises ValueError."""
        # Arrange
        invalid_level = "INVALID_LEVEL"

        # Act & Assert
        with pytest.raises(ValueError, match=f"Invalid log level: {invalid_level}"):
            configure_root_logger(level=invalid_level)

    @patch("shared.logger.logging.basicConfig")
    @patch("shared.logger._suppress_noisy_loggers")
    def test_configure_root_logger_force_true(self, mock_suppress, mock_basic_config):
        """Test that configure_root_logger uses force=True."""
        # Act
        configure_root_logger()

        # Assert
        mock_basic_config.assert_called_once()
        call_kwargs = mock_basic_config.call_args[1]
        assert call_kwargs["force"] is True


@pytest.mark.skip(reason="Logger implementation changed - needs refactor")
class TestReconfigureLogLevel:
    """Test reconfigure_log_level function."""

    @patch("shared.logger.configure_root_logger")
    def test_reconfigure_log_level_success(self, mock_configure):
        """Test reconfigure_log_level with valid level returns True."""
        # Arrange
        valid_level = "DEBUG"

        # Act
        result = reconfigure_log_level(valid_level)

        # Assert
        assert result is True
        mock_configure.assert_called_once_with(level=valid_level)

    @patch("shared.logger.configure_root_logger")
    def test_reconfigure_log_level_invalid_level_returns_false(self, mock_configure):
        """Test reconfigure_log_level with invalid level returns False."""
        # Arrange
        invalid_level = "INVALID_LEVEL"
        mock_configure.side_effect = ValueError("Invalid log level")

        # Act
        result = reconfigure_log_level(invalid_level)

        # Assert
        assert result is False
        mock_configure.assert_called_once_with(level=invalid_level)

    @patch("shared.logger.configure_root_logger")
    @patch("shared.logger.getLogger")
    def test_reconfigure_log_level_logs_success(self, mock_get_logger, mock_configure):
        """Test reconfigure_log_level logs success message."""
        # Arrange
        valid_level = "DEBUG"
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        # Act
        result = reconfigure_log_level(valid_level)

        # Assert
        assert result is True
        mock_logger.info.assert_called_once_with(
            "Log level reconfigured to %s", "DEBUG"
        )


@pytest.mark.skip(reason="Logger implementation changed - needs refactor")
class TestModuleInitialization:
    """Test module initialization behavior."""

    def test_module_logger_created(self):
        """Test that module logger is created and accessible."""
        # Act
        from shared.logger import logger

        # Assert
        assert isinstance(logger, logging.Logger)
        assert logger.name == "shared.logger"
