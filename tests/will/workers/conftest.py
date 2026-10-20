# tests/will/workers/conftest.py
"""Worker unit tests run without the pending-proposal gate's database reads
and without test delivery's git and GitHub calls.

ProposalConsumerWorker.run screens pending proposals first
(will.autonomy.pending_proposal_gate); that pass reads the database, which
unit jobs never provision. Its own behaviour is tested in
tests/will/autonomy/test_pending_proposal_gate.py. Test delivery
(body.infrastructure.delivery_branch) is tested in
tests/body/infrastructure/test_delivery_branch.py.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from body.infrastructure import delivery_branch
from will.autonomy import pending_proposal_gate


@pytest.fixture(autouse=True)
def _no_pending_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        pending_proposal_gate,
        "screen_pending_proposals",
        AsyncMock(return_value=pending_proposal_gate.ScreenOutcome()),
    )


@pytest.fixture(autouse=True)
def _no_test_delivery(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        delivery_branch,
        "run_delivery",
        AsyncMock(return_value=delivery_branch.DeliveryOutcome("none")),
    )
