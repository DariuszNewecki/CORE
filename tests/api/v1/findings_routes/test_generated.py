from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from api.v1.findings_routes import resolve_finding


@pytest.mark.asyncio
# ID: 91195a95-223f-44d7-904f-77503a1328aa
async def test_resolve_finding():
    entry_id = "entry-123"
    payload = AsyncMock()
    payload.reason = "verified as false positive"
    user = {"sub": "user-42", "principal": "governor"}

    resolve = AsyncMock(return_value=1)

    result = await resolve_finding(
        entry_id=entry_id,
        payload=payload,
        resolve=resolve,
        user=user,
    )

    resolve.assert_awaited_once_with(
        entry_id=entry_id,
        reason="verified as false positive",
        resolved_by="governor",
        resolved_by_original="user-42",
        resolution_authority="governor",
    )
    assert result == {
        "ok": True,
        "entry_id": entry_id,
        "status": "resolved",
        "resolved_by": "governor",
        "resolved_by_original": "user-42",
        "resolution_authority": "governor",
    }
