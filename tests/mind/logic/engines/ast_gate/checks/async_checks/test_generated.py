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


# ID: ce5ccd08-b418-42b6-af6b-43a3ac7892ab
def test_AsyncChecks_check_no_module_level_async_engine() -> None:
    source = "engine = create_async_engine('sqlite+aiosqlite://')\n"
    tree = ast.parse(source)

    findings = AsyncChecks.check_no_module_level_async_engine(tree)

    assert isinstance(findings, list)
    assert len(findings) == 1
    assert "create_async_engine()" in findings[0]


# ID: ce87c8e4-d463-4b00-b524-dca160d79213
def test_AsyncChecks() -> None:
    # Happy path for the safe/defensive patterns across the static methods.

    # check_restricted_event_loop_creation: no forbidden calls -> empty findings
    tree = ast.parse("asyncio.run(main())")
    assert AsyncChecks.check_restricted_event_loop_creation(tree, []) == []

    # Defensive get_running_loop + is_running guard makes asyncio.run() safe
    guarded_source = (
        "import asyncio\n"
        "def main():\n"
        "    try:\n"
        "        loop = asyncio.get_running_loop()\n"
        "    except RuntimeError:\n"
        "        loop = None\n"
        "    if loop and loop.is_running():\n"
        "        pass\n"
        "    else:\n"
        "        asyncio.run(other())\n"
    )
    guarded_tree = ast.parse(guarded_source)
    assert (
        AsyncChecks.check_restricted_event_loop_creation(guarded_tree, ["asyncio.run"])
        == []
    )

    # No module-level async engine -> no findings
    safe_module = ast.parse("engine = None\n")
    assert AsyncChecks.check_no_module_level_async_engine(safe_module) == []

    # No import-time async singletons when disallowed list is empty
    assert AsyncChecks.check_no_import_time_async_singletons(safe_module, []) == []

    # Sync function that does not return a Task/Future -> no findings
    sync_fn = ast.parse("def f():\n    return 42\n")
    assert AsyncChecks.check_no_task_return_from_sync_cli(sync_fn) == []


# ID: 3394f48b-5c49-4fc4-86a6-4b2e4ad65fec
def test_AsyncChecks_check_no_import_time_async_singletons():
    source = "client = create_async_client()\n"
    tree = ast.parse(source)

    findings = AsyncChecks.check_no_import_time_async_singletons(
        tree, ["create_async_client"]
    )

    assert len(findings) == 1
    assert "create_async_client()" in findings[0]
    assert "Import-time async singleton creation" in findings[0]

    assert AsyncChecks.check_no_import_time_async_singletons(tree, []) == []





# ID: 5eb75626-1f42-49e4-85e4-a3b5973d95df
def test_AsyncCheckscheck_no_task_return_from_sync_cli():
    source = (
        "def sync_fn():\n"
        "    import asyncio\n"
        "    return asyncio.create_task(do_work())\n"
    )
    tree = ast.parse(source)

    result = AsyncChecks.check_no_task_return_from_sync_cli(tree)

    assert isinstance(result, list)
    assert len(result) == 1
    assert "create_task" not in result[0]
    assert "sync_fn" in result[0]
    assert "returns Task" in result[0]
