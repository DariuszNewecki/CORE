from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

from mind.coherence.checks.dispatch_parity import DispatchParityCheck


# ID: e0f7ae01-89a2-4546-9208-39e3463cd915
def test_DispatchParityCheck_run() -> None:
    check = DispatchParityCheck(repo_root=Path("/tmp"), intent_repo=MagicMock())

    check._load_rule_ids = MagicMock(return_value={"R-001"})
    check._load_mappings = MagicMock(return_value=({"R-001"}, {"R-001": "file_gate"}))
    check._load_substrate_taxonomy = MagicMock(return_value=set())
    check._derive_file_backed_engines = MagicMock(return_value={"file_gate"})

    result = asyncio.run(check.run())

    assert result == []
