"""
Unit tests for _query_symbol_failure_lineage — the ADR-133 D4 per-symbol
circuit breaker's read.

Per-symbol (symbol_name is bound, so the breaker is not per-file) and
lineage-based (ADR-104 D9 as amended 2026-10-03): no rolling time window —
elapsed time never re-arms a capped symbol. The lineage restarts after the
governor resolves a delegated test finding for the file (resolved + human).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch


def _registry(rows):  # type: ignore[no-untyped-def]
    result = MagicMock()
    result.fetchall.return_value = rows
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=None)
    registry = MagicMock()
    registry.session.return_value = cm
    return registry, session


async def test_symbol_name_predicate_bound_in_query() -> None:
    from will.workers.test_remediator._operations import _query_symbol_failure_lineage

    registry, session = _registry([])
    with patch("body.services.service_registry.service_registry", registry):
        count, last = await _query_symbol_failure_lineage("src/foo/bar.py", "sym")

    assert (count, last) == (0, None)
    sql = session.execute.await_args.args[0].text
    params = session.execute.await_args.args[1]
    assert "constitutional_constraints->>'symbol_name'" in sql
    assert params["symbol_name"] == "sym"
    assert params["source_file_json"] == '["src/foo/bar.py"]'


async def test_no_time_window_elapsed_time_never_rearms() -> None:
    """No rolling window: 24h or 7d passing changes nothing."""
    from will.workers.test_remediator._operations import _query_symbol_failure_lineage

    registry, session = _registry([])
    with patch("body.services.service_registry.service_registry", registry):
        await _query_symbol_failure_lineage("src/foo/bar.py", "sym")

    sql = session.execute.await_args.args[0].text
    params = session.execute.await_args.args[1]
    assert "make_interval" not in sql
    assert "interval" not in sql.lower()
    assert "hours" not in params


async def test_lineage_restarts_after_governor_resolution() -> None:
    """Re-arm is explicit governor action: failures before the last
    resolved + human test finding for this file do not count."""
    from will.workers.test_remediator._operations import _query_symbol_failure_lineage

    registry, session = _registry([])
    with patch("body.services.service_registry.service_registry", registry):
        await _query_symbol_failure_lineage("src/foo/bar.py", "sym")

    sql = session.execute.await_args.args[0].text
    assert "b.status = 'resolved'" in sql
    assert "b.resolution_mechanism = 'human'" in sql
    assert "max(b.resolved_at)" in sql
    assert session.execute.await_args.args[1]["source_file"] == "src/foo/bar.py"


async def test_returns_count_and_the_acceptance_gate_reason() -> None:
    from will.workers.test_remediator._operations import _query_symbol_failure_lineage

    results = {
        "flow.build_test_for_symbol:0": {
            "data": {
                "steps": [
                    {
                        "data": {
                            "error": "acceptance_rejected",
                            "details": [
                                "[code.tests.no_unresolved_free_names] Name: 'rule_id'"
                            ],
                        }
                    }
                ]
            }
        }
    }
    rows = [
        ("Actions failed: flow.build_test_for_symbol:0", results),
        ("Actions failed: flow.build_test_for_symbol:0", None),
        ("Actions failed: flow.build_test_for_symbol:0", None),
    ]
    registry, _ = _registry(rows)
    with patch("body.services.service_registry.service_registry", registry):
        count, last = await _query_symbol_failure_lineage("src/foo/bar.py", "sym")

    assert count == 3
    assert last == "[code.tests.no_unresolved_free_names] Name: 'rule_id'"


async def test_returns_zero_on_db_error() -> None:
    """DB errors return (0, None): fail open per the function contract."""
    from will.workers.test_remediator._operations import _query_symbol_failure_lineage

    registry = MagicMock()
    registry.session.side_effect = RuntimeError("db down")
    with patch("body.services.service_registry.service_registry", registry):
        assert await _query_symbol_failure_lineage("src/foo/bar.py", "sym") == (0, None)
