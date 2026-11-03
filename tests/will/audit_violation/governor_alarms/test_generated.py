from __future__ import annotations

import json
from pathlib import Path

from will.audit_violation.governor_alarms import deploy_alarms


# ID: eb2b53fa-f859-4ec9-b178-f12ed92732ad
def test_deploy_alarms(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(
        json.dumps(
            {
                "action": "deploy",
                "ref": "abc123def456",
                "at": "2024-01-01T00:00:00",
                "dev_checkout": "not moved: behind",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    alarms = deploy_alarms(ledger)

    assert isinstance(alarms, list)
    assert len(alarms) == 1
    assert "/opt/dev/CORE" in alarms[0]
    assert "abc123def456" in alarms[0]
    assert "not moved: behind" in alarms[0]


from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
# ID: c28eab8f-7403-468a-9427-2e88cac5bdbe
async def test_open_alarms():
    from will.audit_violation.governor_alarms import ALARMS, STALE_SUBJECT, open_alarms

    mock_board = MagicMock()
    mock_board.fetch_open_finding_subjects_by_prefix = AsyncMock(
        return_value=["some-subject"]
    )

    with (
        patch(
            "will.audit_violation.governor_alarms.BlackboardQueryService",
            return_value=mock_board,
        ),
        patch(
            "will.audit_violation.governor_alarms.deploy_alarms",
            return_value=["deploy alarm text"],
        ) as mock_deploy,
    ):
        ledger = Path("/tmp/ledger.json")
        result = await open_alarms(ledger)

    assert result == [ALARMS[STALE_SUBJECT], "deploy alarm text"]
    mock_board.fetch_open_finding_subjects_by_prefix.assert_awaited_once_with(
        STALE_SUBJECT
    )
    mock_deploy.assert_called_once_with(ledger)
