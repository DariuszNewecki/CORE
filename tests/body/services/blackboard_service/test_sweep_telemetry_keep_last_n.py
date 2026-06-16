"""Tests for ``BlackboardService.sweep_telemetry_keep_last_n_per_subject`` (#568).

Count-based retention for slow-callback telemetry: partition by subject,
keep the most recent N per subject, DELETE the rest (subject to batch_max).

These tests exercise the empty/zero-prefix fail-closed branches with no
DB roundtrip, and pin the SQL parameters that would land on a real
session for cases that DO call into the DB. End-to-end SQL correctness
is verified by the live-DB dry probe in commit body.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from body.services.blackboard_service.blackboard_service import BlackboardService


# ID: 3184c4ad-3129-4907-87cc-68037c5daf05
@pytest.mark.asyncio
async def test_empty_prefixes_is_no_op() -> None:
    """Empty subject_prefixes returns 0 without touching the DB. Fail-closed
    posture per the existing sweep_terminal_telemetry contract — an empty
    allowlist must not result in an over-broad delete.
    """
    svc = BlackboardService()
    with patch("body.services.service_registry.ServiceRegistry") as mock_registry:
        n = await svc.sweep_telemetry_keep_last_n_per_subject(
            subject_prefixes=(), keep_last=100, batch_max=500
        )
    assert n == 0
    mock_registry.session.assert_not_called()


# ID: b57de7dd-0826-4699-95cc-dab5adf641d6
@pytest.mark.asyncio
async def test_keep_last_zero_is_no_op() -> None:
    """``keep_last <= 0`` returns 0 without touching the DB. Mirrors the
    fail-closed posture: an operator who sets keep_last=0 most likely
    misconfigured the YAML rather than intending to wipe all telemetry.
    """
    svc = BlackboardService()
    with patch("body.services.service_registry.ServiceRegistry") as mock_registry:
        n = await svc.sweep_telemetry_keep_last_n_per_subject(
            subject_prefixes=("loop_hold.sample::",), keep_last=0, batch_max=500
        )
    assert n == 0
    mock_registry.session.assert_not_called()


# ID: 9f2beba0-906f-4e25-a2e6-7827c5dc1c0a
@pytest.mark.asyncio
async def test_keep_last_negative_is_no_op() -> None:
    """Negative ``keep_last`` follows the same fail-closed branch as zero."""
    svc = BlackboardService()
    with patch("body.services.service_registry.ServiceRegistry") as mock_registry:
        n = await svc.sweep_telemetry_keep_last_n_per_subject(
            subject_prefixes=("loop_hold.sample::",), keep_last=-5, batch_max=500
        )
    assert n == 0
    mock_registry.session.assert_not_called()


# ID: ac9d5901-4ad2-4349-b2ca-53b0b150e61e
@pytest.mark.asyncio
async def test_valid_inputs_dispatch_sql_with_correct_params() -> None:
    """Valid inputs reach the DB layer with the expected parameters.

    Verifies the wire-up between the public API and the SQL parameters:
    prefixes flow in as a list, keep_last + batch_max as ints.
    """
    svc = BlackboardService()
    fake_result = SimpleNamespace(rowcount=7)
    mock_execute = AsyncMock(return_value=fake_result)

    # Build a session context-manager that yields a session whose .execute
    # is our mock. session.begin() itself returns an async context manager.
    class _SessionCM:
        async def __aenter__(self):
            return SimpleNamespace(
                execute=mock_execute,
                begin=lambda: _BeginCM(),
            )

        async def __aexit__(self, *a):
            return False

    class _BeginCM:
        async def __aenter__(self):
            return None

        async def __aexit__(self, *a):
            return False

    with patch("body.services.service_registry.ServiceRegistry") as mock_registry:
        mock_registry.session.return_value = _SessionCM()
        n = await svc.sweep_telemetry_keep_last_n_per_subject(
            subject_prefixes=("loop_hold.sample::", "other.telemetry::"),
            keep_last=100,
            batch_max=500,
        )

    assert n == 7
    mock_execute.assert_awaited_once()
    # Inspect the kwargs passed to execute — the second positional arg is
    # the bind-params dict.
    args, _ = mock_execute.call_args
    params = args[1]
    assert params == {
        "prefixes": ["loop_hold.sample::", "other.telemetry::"],
        "keep_last": 100,
        "batch_max": 500,
    }


# ID: 8990361b-407a-4b7a-9766-33a55915c8d3
@pytest.mark.asyncio
async def test_returns_zero_when_rowcount_is_none() -> None:
    """PostgreSQL returns ``rowcount=None`` in some edge cases; the method
    coerces that to 0 so callers see a clean integer count.
    """
    svc = BlackboardService()
    fake_result = SimpleNamespace(rowcount=None)
    mock_execute = AsyncMock(return_value=fake_result)

    class _SessionCM:
        async def __aenter__(self):
            return SimpleNamespace(execute=mock_execute, begin=lambda: _BeginCM())

        async def __aexit__(self, *a):
            return False

    class _BeginCM:
        async def __aenter__(self):
            return None

        async def __aexit__(self, *a):
            return False

    with patch("body.services.service_registry.ServiceRegistry") as mock_registry:
        mock_registry.session.return_value = _SessionCM()
        n = await svc.sweep_telemetry_keep_last_n_per_subject(
            subject_prefixes=("loop_hold.sample::",),
            keep_last=100,
            batch_max=500,
        )
    assert n == 0


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
