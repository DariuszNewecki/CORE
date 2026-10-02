# tests/body/atomic/test_registry__registration_log_level.py
"""#914: action registration logs at DEBUG, not INFO.

It fires once per action at import time, so at INFO every core-admin
invocation (--help included) printed ~40 lines before doing anything.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from body.atomic import registry
from body.atomic.registry import ActionCategory, register_action


# ID: 212caf1e-c03b-486a-a06e-83bafc370e08
def test_registration_logs_at_debug_not_info(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_logger = MagicMock()
    monkeypatch.setattr(registry, "logger", fake_logger)
    monkeypatch.setattr(registry, "_validate_action_signature", lambda _f: None)
    monkeypatch.setattr(registry, "action_registry", MagicMock())

    async def _dummy(**kwargs):  # pragma: no cover - never executed
        return None

    register_action(
        action_id="test.log_level_probe",
        description="probe",
        category=ActionCategory.CHECK,
        policies=[],
    )(_dummy)

    fake_logger.debug.assert_called_once()
    assert "registered successfully" in fake_logger.debug.call_args.args[0]
    fake_logger.info.assert_not_called()
