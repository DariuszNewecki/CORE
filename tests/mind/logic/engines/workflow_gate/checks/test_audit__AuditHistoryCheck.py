"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/mind/logic/engines/workflow_gate/checks/audit.py
- Symbol: AuditHistoryCheck
- Generated: 2026-01-11 02:41:42
- 2026-06-07 (#572 Cat B batch 19): file_path=None on its own no longer
  short-circuits to []. The actual "no findings" branch requires a
  valid DB session to be reached — without one, source's broad except
  emits a "System Sensation Error: Audit Ledger (DB) is unreachable."
  string. Test pinned to the current sensation-error behavior; deeper
  coverage of the audit-history happy path belongs in an integration
  suite with a real Audit Ledger session.
"""

import pytest

from mind.logic.engines.workflow_gate.checks.audit import AuditHistoryCheck


@pytest.mark.asyncio
async def test_verify_no_db_session_returns_sensation_error():
    """When no DB session is plumbed through params, the verify() flow
    falls into the broad except path and returns a single Audit-Ledger-
    unreachable string. ``file_path=None`` is a no-op detail here — the
    sensation error fires regardless because no session was available."""
    check = AuditHistoryCheck()
    result = await check.verify(file_path=None, params={})
    assert result == ["System Sensation Error: Audit Ledger (DB) is unreachable."]
