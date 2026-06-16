# tests/api/v1/test_lane_routes.py

"""Unit tests for lane_routes — Assisted Remediation Lane (ADR-109 #652).

Covers GET /lane (list delegated findings). Mocks the Will-layer
LaneService the route routes through; the route runs no action and owns no
session, so the only collaborator to stub is list_delegated_findings.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from api.v1.lane_routes import list_delegated_findings


def _mk_finding(fid: str = "f-1") -> dict:
    return {
        "id": fid,
        "subject": "purity.no_orphan_files::src/x.py",
        "payload": {"rule": "purity.no_orphan_files"},
        "created_at": "2026-06-16T07:00:00",
    }


@pytest.mark.asyncio
async def test_list_delegated_wraps_findings_in_count_envelope():
    """The route delegates to LaneService.list_delegated_findings and wraps
    the result in {count, findings}, forwarding the limit."""
    service = AsyncMock()
    service.list_delegated_findings = AsyncMock(return_value=[_mk_finding()])

    with patch("api.v1.lane_routes.LaneService", return_value=service):
        out = await list_delegated_findings(limit=25)

    assert out["count"] == 1
    assert out["findings"] == [_mk_finding()]
    service.list_delegated_findings.assert_awaited_once_with(limit=25)


@pytest.mark.asyncio
async def test_list_delegated_empty_returns_zero_count():
    """An empty lane returns count=0 and an empty list, not an error."""
    service = AsyncMock()
    service.list_delegated_findings = AsyncMock(return_value=[])

    with patch("api.v1.lane_routes.LaneService", return_value=service):
        out = await list_delegated_findings(limit=50)

    assert out == {"count": 0, "findings": []}
