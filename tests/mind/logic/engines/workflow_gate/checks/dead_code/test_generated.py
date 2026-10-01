from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mind.logic.engines.workflow_gate.checks.dead_code import DeadCodeCheck


@pytest.mark.asyncio
# ID: ec10467d-a49d-4b4f-8314-db1667afb948
async def test_DeadCodeCheck_verify() -> None:
    path_resolver = MagicMock()
    path_resolver.repo_root = Path("/repo")

    check = DeadCodeCheck(path_resolver)

    fake_result = MagicMock()
    fake_result.stdout = "unused_var at line 10\nanother_dead at line 20\n"

    with patch(
        "mind.logic.engines.workflow_gate.checks.dead_code.run_vulture",
        new=AsyncMock(return_value=fake_result),
    ) as mock_run_vulture:
        violations = await check.verify(
            file_path=Path("/repo/src/module.py"),
            params={"confidence": 90},
        )

    assert violations == [
        "Dead code detected: unused_var at line 10",
        "Dead code detected: another_dead at line 20",
    ]
    mock_run_vulture.assert_awaited_once_with(
        target="/repo/src/module.py",
        repo_root=Path("/repo"),
        confidence=90,
    )
