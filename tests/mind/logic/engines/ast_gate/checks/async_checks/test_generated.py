from __future__ import annotations

import ast
from unittest.mock import patch

from mind.logic.engines.ast_gate.checks.async_checks import AsyncChecks


# ID: c0f4a4d4-5a0b-4f3b-b55b-c5317f61aa18
def test_check_no_task_return_from_sync_cli() -> None:
    source = (
        "import asyncio\ndef sync_handler():\n    return asyncio.create_task(other())\n"
    )
    tree = ast.parse(source)

    with (
        patch(
            "mind.logic.engines.ast_gate.checks.async_checks.ASTHelpers.full_attr_name",
            return_value="asyncio.create_task",
        ),
        patch(
            "mind.logic.engines.ast_gate.checks.async_checks.ASTHelpers.lineno",
            return_value=3,
        ),
    ):
        findings = AsyncChecks.check_no_task_return_from_sync_cli(tree)

    assert findings == ["Line 3: Sync function 'sync_handler' returns Task"]
