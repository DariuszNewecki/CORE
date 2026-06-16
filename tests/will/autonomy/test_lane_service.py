# tests/will/autonomy/test_lane_service.py

"""Unit tests for LaneService — Assisted Remediation Lane (ADR-109 #652).

LaneService is the Will-layer facade the lane API routes through. It owns no
state and no session; it delegates to the BlackboardService obtained from the
service_registry. The test stubs that registry call and asserts the limit is
forwarded and the rows passed straight back.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from will.autonomy.lane_service import LaneService


@pytest.mark.asyncio
async def test_list_delegated_findings_delegates_to_blackboard():
    """list_delegated_findings forwards the limit to
    BlackboardService.fetch_delegated_findings and returns its rows verbatim."""
    rows = [{"id": "f-1", "subject": "s", "payload": {}, "created_at": None}]

    bb_service = AsyncMock()
    bb_service.fetch_delegated_findings = AsyncMock(return_value=rows)

    with patch(
        "will.autonomy.lane_service.service_registry.get_blackboard_service",
        AsyncMock(return_value=bb_service),
    ):
        out = await LaneService().list_delegated_findings(limit=10)

    assert out == rows
    bb_service.fetch_delegated_findings.assert_awaited_once_with(limit=10)
