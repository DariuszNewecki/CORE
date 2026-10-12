# tests/api/v1/test_findings_resolve_route.py
"""POST /findings/{id}/resolve: the server stamps the governor (ADR-132 D10.4)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from api.v1.findings_routes import ResolveFindingRequest, resolve_finding


_GOVERNOR = {"sub": "darek", "principal": "principal.governor"}


async def test_actor_and_authority_come_from_the_verified_caller() -> None:
    resolve = AsyncMock(return_value=1)
    out = await resolve_finding(
        entry_id="e-1",
        payload=ResolveFindingRequest(reason="stale"),
        resolve=resolve,
        user=_GOVERNOR,
    )
    resolve.assert_awaited_once_with(
        entry_id="e-1",
        reason="stale",
        resolved_by="darek",
        resolution_authority="principal.governor",
    )
    assert out["resolved_by"] == "darek"
    assert out["resolution_authority"] == "principal.governor"


def test_the_body_cannot_name_the_actor() -> None:
    body = ResolveFindingRequest.model_validate(
        {"reason": "x", "resolved_by": "core-claude", "resolution_authority": "y"}
    )
    assert body.model_dump() == {"reason": "x"}


def test_a_reason_is_required() -> None:
    with pytest.raises(ValidationError):
        ResolveFindingRequest(reason="")


async def test_not_delegated_or_unknown_is_404() -> None:
    with pytest.raises(HTTPException) as exc:
        await resolve_finding(
            entry_id="e-1",
            payload=ResolveFindingRequest(reason="stale"),
            resolve=AsyncMock(return_value=0),
            user=_GOVERNOR,
        )
    assert exc.value.status_code == 404
