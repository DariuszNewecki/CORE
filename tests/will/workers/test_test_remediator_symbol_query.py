"""
Unit tests for _query_recent_symbol_failures SQL predicate correctness.

Verifies that symbol_name is bound into the query so the ADR-133 D4
circuit breaker is per-symbol, not per-file.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch


async def test_symbol_name_predicate_bound_in_query() -> None:
    """
    SQL must include constitutional_constraints->>'symbol_name' and bind the
    caller-supplied symbol_name into the params dict.  Without this the
    per-symbol circuit breaker (ADR-133 D4) is effectively per-file.
    """
    from will.workers.test_remediator._operations import _query_recent_symbol_failures

    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 0

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    mock_registry = MagicMock()
    mock_registry.session.return_value = mock_cm

    with patch("body.services.service_registry.service_registry", mock_registry):
        count = await _query_recent_symbol_failures(
            "src/foo/bar.py", "target_symbol", lookback_hours=12
        )

    assert count == 0
    mock_session.execute.assert_awaited_once()
    call_args = mock_session.execute.await_args

    sql_clause = call_args.args[0]
    assert "constitutional_constraints->>'symbol_name'" in sql_clause.text

    params = call_args.args[1]
    assert params["symbol_name"] == "target_symbol"
    assert params["source_file_json"] == '["src/foo/bar.py"]'
    assert params["hours"] == 12


async def test_distinct_symbols_same_file_are_independent() -> None:
    """
    Two calls with the same source_file but different symbol_names must
    pass distinct symbol_name values — confirming the per-symbol boundary.
    """
    from will.workers.test_remediator._operations import _query_recent_symbol_failures

    captured: list[dict] = []

    async def _fake_execute(clause, params):  # type: ignore[no-untyped-def]
        captured.append(dict(params))
        result = MagicMock()
        result.scalar_one.return_value = 0
        return result

    mock_session = AsyncMock()
    mock_session.execute = _fake_execute

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    mock_registry = MagicMock()
    mock_registry.session.return_value = mock_cm

    with patch("body.services.service_registry.service_registry", mock_registry):
        await _query_recent_symbol_failures("src/foo/bar.py", "symbol_a")
        await _query_recent_symbol_failures("src/foo/bar.py", "symbol_b")

    assert len(captured) == 2
    assert captured[0]["symbol_name"] == "symbol_a"
    assert captured[1]["symbol_name"] == "symbol_b"


async def test_returns_zero_on_db_error() -> None:
    """DB errors must return 0 (fail open) per the function contract."""
    from will.workers.test_remediator._operations import _query_recent_symbol_failures

    mock_registry = MagicMock()
    mock_registry.session.side_effect = RuntimeError("db down")

    with patch("body.services.service_registry.service_registry", mock_registry):
        count = await _query_recent_symbol_failures("src/foo/bar.py", "sym")

    assert count == 0
