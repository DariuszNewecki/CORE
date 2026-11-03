from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from will.autonomy.circuit_breaker import trip


@pytest.mark.asyncio
# ID: dd9ac200-84cc-4fa1-ae9e-5a0ebb550fd3
async def test_trip() -> None:
    worker = MagicMock()
    worker.post_observation = AsyncMock(return_value=None)

    findings = [{"id": "f1"}, {"id": "f2"}]
    mark_delegated = AsyncMock(return_value=2)

    await trip(
        worker=worker,
        ref_id="ref-123",
        ref_kind="violation",
        file_path="src/example.py",
        findings=findings,
        count=3,
        signature="sig-abc",
        last_proposal_id="prop-42",
        last_failure_reason="boom",
        mark_delegated=mark_delegated,
    )

    mark_delegated.assert_awaited_once_with(findings)
    worker.post_observation.assert_awaited_once()
    _, kwargs = worker.post_observation.await_args
    assert kwargs["subject"] == "governance.circuit_breaker_tripped"
    assert kwargs["status"] == "abandoned"
    payload = kwargs["payload"]
    assert payload["ref_id"] == "ref-123"
    assert payload["ref_kind"] == "violation"
    assert payload["file_path"] == "src/example.py"
    assert payload["failure_count"] == 3
    assert payload["error_signature"] == "sig-abc"
    assert payload["last_proposal_id"] == "prop-42"
    assert payload["last_failure_reason"] == "boom"
    assert payload["findings_delegated"] == 2
