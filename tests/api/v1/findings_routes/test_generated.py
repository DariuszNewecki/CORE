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


import asyncio
from unittest.mock import MagicMock

from api.v1.findings_routes import get_finding_chain


# ID: c7b538c2-3bbe-46a9-9f53-2a1d64f2bd5a
def test_get_finding_chain():
    entry_id = "entry-123"
    proposal_id = "proposal-456"
    expected_chain = {"proposal_id": proposal_id, "steps": ["a", "b"]}

    svc = MagicMock()
    svc.get_finding_proposal_link = AsyncMock(return_value=proposal_id)
    svc.get_chain_for_proposal = AsyncMock(return_value=expected_chain)

    session = MagicMock()

    result = asyncio.run(get_finding_chain(entry_id, svc, session))

    assert result == expected_chain
    svc.get_finding_proposal_link.assert_awaited_once_with(entry_id, session)
    svc.get_chain_for_proposal.assert_awaited_once_with(proposal_id, session)
