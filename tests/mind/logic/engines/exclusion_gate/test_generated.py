from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from mind.logic.engines.exclusion_gate import find_dead_excludes


# ID: 5c53d705-27b8-4002-92e5-ca4bd051e7d7
def test_find_dead_excludes() -> None:
    rule = SimpleNamespace(
        rule_id="rule-1",
        scope=["src/**"],
        exclusions=["src/**"],
        is_context_level=False,
        engine="ast_gate",
    )

    probe = AsyncMock(return_value=True)

    with patch(
        "mind.governance.audit_context._include_matches",
        side_effect=lambda path, pattern: (
            pattern == "src/**" and path.startswith("src/")
        ),
    ):
        result = asyncio.run(
            find_dead_excludes(
                rules=[rule],
                repo_files=["src/a.py", "src/b.py"],
                repo_root=Path("/repo"),
                probe=probe,
            )
        )

    assert result == []
