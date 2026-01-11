"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/shared/errors.py
- Symbol: register_exception_handlers
- Status: 1 tests passed, some failed
- Passing tests: test_register_exception_handlers_info_log
- Generated: 2026-01-11 01:15:28
"""

import logging

from fastapi import FastAPI

from shared.errors import register_exception_handlers


def test_register_exception_handlers_info_log(caplog):
    """Test that the function logs an info message upon registration."""
    app = FastAPI()
    caplog.set_level(logging.INFO)
    register_exception_handlers(app)
    assert "Registered global exception handlers." in caplog.text
