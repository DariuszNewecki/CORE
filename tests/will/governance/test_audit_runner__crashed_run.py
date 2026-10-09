"""#947 -- an async audit run that crashes is stored as DEGRADED.

`run_and_persist_audit` pre-inserts a row with verdict 'pending'. When the
audit raised, the failure branch set status='failed' and left the verdict
'pending', so the stored run never said that it could not decide.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from will.governance import audit_runner


async def test_crashed_run_is_stored_failed_and_degraded() -> None:
    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    with (
        patch.object(
            audit_runner,
            "run_audit_workflow",
            new=AsyncMock(side_effect=RuntimeError("engine exploded")),
        ),
        pytest.raises(RuntimeError, match="engine exploded"),
    ):
        await audit_runner.run_and_persist_audit(
            SimpleNamespace(), session, run_id="00000000-0000-0000-0000-000000000001"
        )
    sql = str(session.execute.await_args.args[0])
    params = session.execute.await_args.args[1]
    assert "status = 'failed'" in sql
    assert "verdict = :verdict" in sql
    assert params["verdict"] == "DEGRADED"
    session.commit.assert_awaited()
