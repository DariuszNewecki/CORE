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
