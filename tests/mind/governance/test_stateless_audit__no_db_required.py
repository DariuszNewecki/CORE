"""F-10.1a — assert stateless audit never touches the DB.

Constitutional guarantee for ADR-085 D5's F-10 exit criterion: when
the gate runs in an external repo's CI with no Postgres reachable,
the audit must complete without attempting a DB connection. A
regression that re-introduces a session call would break the CI gate
silently — this test makes that regression a test failure.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mind.governance.audit_context import AuditorContext


pytestmark = [pytest.mark.integration]


async def test_stateless_context_skips_knowledge_graph_load() -> None:
    """Stateless mode: load_knowledge_graph short-circuits without DB call.

    The pre-F-10.1a behaviour was to *try* KnowledgeService and catch the
    DB-connection exception. That worked but spammed the log with errors
    on every CI run. Stateless mode now fast-paths the no-op so the gate
    never attempts a connection in the first place.
    """
    context = AuditorContext(repo_path=Path("/test/repo"), stateless=True)
    with patch("mind.governance.audit_context.KnowledgeService") as mock_service_class:
        await context.load_knowledge_graph()
        mock_service_class.assert_not_called()
    assert context.knowledge_graph == {"symbols": {}}
    assert context.symbols_map == {}


async def test_non_stateless_context_still_attempts_knowledge_graph() -> None:
    """Regression guard: stateless=False keeps the legacy code path.

    The daemon and core-api still rely on the DB-backed knowledge graph;
    F-10.1a must not break that path. A failure here would mean the
    stateless flag leaked into the default code path.
    """
    context = AuditorContext(repo_path=Path("/test/repo"), stateless=False)
    mock_graph = {"symbols": {"X": {}}}
    with patch("mind.governance.audit_context.KnowledgeService") as mock_service_class:
        mock_service_instance = MagicMock()
        mock_service_instance.get_graph = AsyncMock(return_value=mock_graph)
        mock_service_class.return_value = mock_service_instance
        await context.load_knowledge_graph()
        mock_service_class.assert_called_once_with(context.repo_path)


async def test_stateless_context_skips_llm_gate_cache_sweep() -> None:
    """Stateless mode: sweep_llm_gate_cache short-circuits to 0.

    The DB-backed verdict cache table is unreachable; the sweep cannot
    do anything useful even if attempted. Belt-and-suspenders: the
    method already returns 0 when db_session is None, but the explicit
    stateless check documents the invariant and avoids the latch flip
    that would otherwise prevent a downstream consumer (a future test
    runner) from invoking the real path.
    """
    context = AuditorContext(repo_path=Path("/test/repo"), stateless=True)
    purged = await context.sweep_llm_gate_cache()
    assert purged == 0
    assert context._llm_gate_cache_swept is True


def test_stateless_flag_defaults_to_false() -> None:
    """Stateless mode is opt-in; default behaviour is unchanged.

    Existing callers (the daemon's AuditViolationSensor, core-api's
    run_sync_audit, and the legacy core-admin code audit CLI path) all
    expect db_session-backed behaviour and must continue to get it.
    """
    context = AuditorContext(repo_path=Path("/test/repo"))
    assert context.stateless is False
