# tests/api/v1/test_lane_routes.py

"""Unit tests for lane_routes — Assisted Remediation Lane (ADR-109 #652).

Covers GET /lane (list delegated findings). Mocks the Will-layer
LaneService the route routes through; the route runs no action and owns no
session, so the only collaborator to stub is list_delegated_findings.
"""

from __future__ import annotations

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from api.v1.lane_routes import (
    ProposeRequest,
    list_delegated_findings,
    propose_diff,
)


def _mk_finding(fid: str = "f-1") -> dict:
    return {
        "id": fid,
        "subject": "purity.no_orphan_files::src/x.py",
        "payload": {"rule": "purity.no_orphan_files"},
        "created_at": "2026-06-16T07:00:00",
    }


_PATCH = "--- a/src/x.py\n+++ b/src/x.py\n"


def _session_returning(row: dict | None) -> AsyncMock:
    """A session stub whose execute().mappings().first() yields *row*."""
    session = AsyncMock()
    exec_result = MagicMock()
    exec_result.mappings.return_value.first.return_value = row
    session.execute = AsyncMock(return_value=exec_result)
    return session


def _fix_row(*, ok: bool, patch: str = _PATCH, production_set=None) -> dict:
    """A core.fix_runs row mapping for a completed assisted.validate_diff run."""
    return {
        "fix_id": "assisted.validate_diff",
        "status": "completed",
        "result": {
            "ok": ok,
            "data": {
                "validation_results": {"patch_applies": ok, "ruff": ok},
                "production_set": production_set or ["src/x.py"],
                "patch_sha256": hashlib.sha256(patch.encode("utf-8")).hexdigest(),
            },
        },
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


# --- propose: the verdict gate ------------------------------------------------


@pytest.mark.asyncio
async def test_propose_rejects_unknown_validation_run():
    """No fix_runs row for the named run → 422, no proposal created."""
    body = ProposeRequest(patch=_PATCH, validation_run_id="missing")
    service = AsyncMock()
    with patch("api.v1.lane_routes.LaneService", return_value=service):
        with pytest.raises(HTTPException) as exc:
            await propose_diff(
                finding_id="f-1", body=body, session=_session_returning(None)
            )
    assert exc.value.status_code == 422
    service.propose_validated_diff.assert_not_called()


@pytest.mark.asyncio
async def test_propose_rejects_failed_validation():
    """A run that did not pass cannot become a proposal (422)."""
    body = ProposeRequest(patch=_PATCH, validation_run_id="run-1")
    service = AsyncMock()
    with patch("api.v1.lane_routes.LaneService", return_value=service):
        with pytest.raises(HTTPException) as exc:
            await propose_diff(
                finding_id="f-1",
                body=body,
                session=_session_returning(_fix_row(ok=False)),
            )
    assert exc.value.status_code == 422
    service.propose_validated_diff.assert_not_called()


@pytest.mark.asyncio
async def test_propose_rejects_patch_mismatch():
    """A passing verdict bound to different bytes than submitted → 422.

    Guards the realistic mistake: the agent edits the diff after validating
    and forgets to re-validate."""
    body = ProposeRequest(patch="DIFFERENT BYTES\n", validation_run_id="run-1")
    service = AsyncMock()
    with patch("api.v1.lane_routes.LaneService", return_value=service):
        with pytest.raises(HTTPException) as exc:
            await propose_diff(
                finding_id="f-1",
                body=body,
                session=_session_returning(_fix_row(ok=True)),
            )
    assert exc.value.status_code == 422
    service.propose_validated_diff.assert_not_called()


@pytest.mark.asyncio
async def test_propose_rejects_non_validate_run():
    """A run id that points at some other action is refused (422)."""
    body = ProposeRequest(patch=_PATCH, validation_run_id="run-1")
    row = _fix_row(ok=True)
    row["fix_id"] = "fix.docstrings"
    service = AsyncMock()
    with patch("api.v1.lane_routes.LaneService", return_value=service):
        with pytest.raises(HTTPException) as exc:
            await propose_diff(
                finding_id="f-1", body=body, session=_session_returning(row)
            )
    assert exc.value.status_code == 422
    service.propose_validated_diff.assert_not_called()


@pytest.mark.asyncio
async def test_propose_happy_path_creates_proposal():
    """A passing, patch-bound verdict routes to LaneService and returns the
    draft proposal envelope with the verified production set."""
    body = ProposeRequest(patch=_PATCH, validation_run_id="run-1")
    service = AsyncMock()
    service.propose_validated_diff = AsyncMock(return_value="prop-xyz")

    with patch("api.v1.lane_routes.LaneService", return_value=service):
        out = await propose_diff(
            finding_id="f-1",
            body=body,
            session=_session_returning(
                _fix_row(ok=True, production_set=["src/x.py", "src/base.py"])
            ),
        )

    assert out == {
        "proposal_id": "prop-xyz",
        "status": "draft",
        "approval_required": True,
        "scope_files": ["src/x.py", "src/base.py"],
    }
    service.propose_validated_diff.assert_awaited_once_with(
        finding_id="f-1",
        patch=_PATCH,
        production_set=["src/x.py", "src/base.py"],
    )
