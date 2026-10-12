# tests/will/workers/conftest.py
"""Worker unit tests run without the pending-proposal gate's database reads.

ProposalConsumerWorker.run screens pending proposals first
(will.autonomy.pending_proposal_gate); that pass reads the database, which
unit jobs never provision. Its own behaviour is tested in
tests/will/autonomy/test_pending_proposal_gate.py.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from will.autonomy import pending_proposal_gate


@pytest.fixture(autouse=True)
def _no_pending_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        pending_proposal_gate,
        "screen_pending_proposals",
        AsyncMock(return_value=pending_proposal_gate.ScreenOutcome()),
    )
