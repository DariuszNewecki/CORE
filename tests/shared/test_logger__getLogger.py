"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/shared/logger.py
- Symbol: getLogger
- Status: verified_in_sandbox
- Generated: 2026-01-11 01:07:15
"""

import logging

from shared.logger import getLogger


# Detected return type: logging.Logger


def test_getlogger_returns_logger_instance():
    """Test that getLogger returns a logging.Logger instance."""
    logger = getLogger()
    assert isinstance(logger, logging.Logger)


def test_getlogger_with_none_returns_root_logger():
    """Test that getLogger with None returns the root logger."""
    logger = getLogger(None)
    assert logger is logging.getLogger()


def test_getlogger_with_name_returns_named_logger():
    """Test that getLogger with a name returns the appropriate named logger."""
    logger = getLogger("test_logger")
    assert logger is logging.getLogger("test_logger")


def test_getlogger_with_empty_string():
    """Test that getLogger with empty string returns root logger."""
    logger = getLogger("")
    assert logger is logging.getLogger("")


def test_getlogger_with_same_name_returns_same_instance():
    """Test that getLogger with the same name returns the same instance."""
    logger1 = getLogger("shared_module")
    logger2 = getLogger("shared_module")
    assert logger1 is logger2


def test_getlogger_with_different_names_returns_different_loggers():
    """Test that getLogger with different names returns different loggers."""
    logger1 = getLogger("module_a")
    logger2 = getLogger("module_b")
    assert logger1 is not logger2
    assert logger1.name == "module_a"
    assert logger2.name == "module_b"


def test_getlogger_with_nested_module_name():
    """Test that getLogger works with dotted module names."""
    logger = getLogger("shared.logger.submodule")
    assert logger is logging.getLogger("shared.logger.submodule")
    assert logger.name == "shared.logger.submodule"
