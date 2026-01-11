"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/mind/logic/engines/ast_gate/checks/async_checks.py
- Symbol: AsyncChecks
- Status: 18 tests passed, some failed
- Passing tests: test_empty_forbidden_calls_returns_empty_list, test_direct_run_until_complete_detected, test_chained_get_event_loop_run_until_complete_detected, test_safe_get_event_loop_not_detected, test_unguarded_asyncio_run_detected, test_new_event_loop_detected, test_multiple_violations_all_detected, test_empty_disallowed_calls_returns_empty_list, test_module_level_disallowed_call_detected, test_multiple_module_level_calls_detected, test_no_engine_creation_returns_empty, test_module_level_create_async_engine_detected, test_fully_qualified_create_async_engine_detected, test_annassign_create_async_engine_detected, test_function_level_create_async_engine_not_detected, test_no_sync_functions_returns_empty, test_async_function_returning_task_not_detected, test_sync_function_returning_other_value_not_detected
- Generated: 2026-01-11 02:30:29
"""

import ast

from mind.logic.engines.ast_gate.checks.async_checks import AsyncChecks


class TestCheckRestrictedEventLoopCreation:

    def test_empty_forbidden_calls_returns_empty_list(self):
        """When forbidden_calls is empty, should return empty list."""
        tree = ast.parse("import asyncio")
        result = AsyncChecks.check_restricted_event_loop_creation(tree, [])
        assert result == []

    def test_direct_run_until_complete_detected(self):
        """Direct loop.run_until_complete() should be detected."""
        code = "\nimport asyncio\nloop = asyncio.get_event_loop()\nloop.run_until_complete(some_func())\n"
        tree = ast.parse(code)
        result = AsyncChecks.check_restricted_event_loop_creation(
            tree, ["asyncio.new_event_loop"]
        )
        assert len(result) == 1
        assert "run_until_complete" in result[0]

    def test_chained_get_event_loop_run_until_complete_detected(self):
        """Chained asyncio.get_event_loop().run_until_complete() should be detected."""
        code = "asyncio.get_event_loop().run_until_complete(some_func())"
        tree = ast.parse(code)
        result = AsyncChecks.check_restricted_event_loop_creation(
            tree, ["asyncio.new_event_loop"]
        )
        assert len(result) == 1
        assert "get_event_loop().run_until_complete()" in result[0]

    def test_safe_get_event_loop_not_detected(self):
        """asyncio.get_event_loop() without run_until_complete should be safe."""
        code = '\nimport asyncio\nloop = asyncio.get_event_loop()\nif loop.is_running():\n    print("Loop is running")\n'
        tree = ast.parse(code)
        result = AsyncChecks.check_restricted_event_loop_creation(
            tree, ["asyncio.new_event_loop"]
        )
        assert result == []

    def test_unguarded_asyncio_run_detected(self):
        """asyncio.run() without defensive guard should be detected."""
        code = "\nimport asyncio\nasync def main():\n    pass\nasyncio.run(main())\n"
        tree = ast.parse(code)
        result = AsyncChecks.check_restricted_event_loop_creation(
            tree, ["asyncio.new_event_loop"]
        )
        assert len(result) == 1
        assert "asyncio.run() without defensive loop check" in result[0]

    def test_new_event_loop_detected(self):
        """asyncio.new_event_loop() should be detected when in forbidden_calls."""
        code = "loop = asyncio.new_event_loop()"
        tree = ast.parse(code)
        result = AsyncChecks.check_restricted_event_loop_creation(
            tree, ["asyncio.new_event_loop"]
        )
        assert len(result) == 1
        assert "new_event_loop" in result[0]

    def test_multiple_violations_all_detected(self):
        """Multiple violations in same code should all be detected."""
        code = "\nimport asyncio\nloop = asyncio.new_event_loop()\nloop.run_until_complete(func1())\nasyncio.run(func2())\n"
        tree = ast.parse(code)
        result = AsyncChecks.check_restricted_event_loop_creation(
            tree, ["asyncio.new_event_loop"]
        )
        assert len(result) == 3


class TestCheckNoImportTimeAsyncSingletons:

    def test_empty_disallowed_calls_returns_empty_list(self):
        """When disallowed_calls is empty, should return empty list."""
        tree = ast.parse("import asyncio")
        result = AsyncChecks.check_no_import_time_async_singletons(tree, [])
        assert result == []

    def test_module_level_disallowed_call_detected(self):
        """Module-level disallowed call should be detected."""
        code = "\nimport asyncio\nimport aiohttp\nconnector = aiohttp.TCPConnector()\n"
        tree = ast.parse(code)
        result = AsyncChecks.check_no_import_time_async_singletons(
            tree, ["aiohttp.TCPConnector"]
        )
        assert len(result) == 1
        assert "TCPConnector()" in result[0]

    def test_multiple_module_level_calls_detected(self):
        """Multiple module-level disallowed calls should all be detected."""
        code = "\nimport aiohttp\nimport asyncio\nc1 = aiohttp.TCPConnector()\nc2 = aiohttp.TCPConnector()\n"
        tree = ast.parse(code)
        result = AsyncChecks.check_no_import_time_async_singletons(
            tree, ["aiohttp.TCPConnector"]
        )
        assert len(result) == 2


class TestCheckNoModuleLevelAsyncEngine:

    def test_no_engine_creation_returns_empty(self):
        """Code without async engine creation should return empty list."""
        code = '\nfrom sqlalchemy import create_engine\nengine = create_engine("sqlite://")\n'
        tree = ast.parse(code)
        result = AsyncChecks.check_no_module_level_async_engine(tree)
        assert result == []

    def test_module_level_create_async_engine_detected(self):
        """Module-level create_async_engine() should be detected."""
        code = '\nfrom sqlalchemy.ext.asyncio import create_async_engine\nengine = create_async_engine("sqlite+aiosqlite://")\n'
        tree = ast.parse(code)
        result = AsyncChecks.check_no_module_level_async_engine(tree)
        assert len(result) == 1
        assert "create_async_engine" in result[0]

    def test_fully_qualified_create_async_engine_detected(self):
        """Fully qualified sqlalchemy.ext.asyncio.create_async_engine should be detected."""
        code = '\nimport sqlalchemy.ext.asyncio\nengine = sqlalchemy.ext.asyncio.create_async_engine("sqlite+aiosqlite://")\n'
        tree = ast.parse(code)
        result = AsyncChecks.check_no_module_level_async_engine(tree)
        assert len(result) == 1

    def test_annassign_create_async_engine_detected(self):
        """Annotated assignment with create_async_engine should be detected."""
        code = '\nfrom sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine\nengine: AsyncEngine = create_async_engine("sqlite+aiosqlite://")\n'
        tree = ast.parse(code)
        result = AsyncChecks.check_no_module_level_async_engine(tree)
        assert len(result) == 1

    def test_function_level_create_async_engine_not_detected(self):
        """create_async_engine() inside function should NOT be detected."""
        code = '\nfrom sqlalchemy.ext.asyncio import create_async_engine\ndef setup():\n    engine = create_async_engine("sqlite+aiosqlite://")\n'
        tree = ast.parse(code)
        result = AsyncChecks.check_no_module_level_async_engine(tree)
        assert result == []


class TestCheckNoTaskReturnFromSyncCli:

    def test_no_sync_functions_returns_empty(self):
        """Code without sync functions should return empty list."""
        code = (
            "\nimport asyncio\nasync def main():\n    return await asyncio.sleep(1)\n"
        )
        tree = ast.parse(code)
        result = AsyncChecks.check_no_task_return_from_sync_cli(tree)
        assert result == []

    def test_async_function_returning_task_not_detected(self):
        """Async function returning Task should NOT be detected."""
        code = "\nimport asyncio\nasync def process():\n    task = asyncio.create_task(coro())\n    return task\n"
        tree = ast.parse(code)
        result = AsyncChecks.check_no_task_return_from_sync_cli(tree)
        assert result == []

    def test_sync_function_returning_other_value_not_detected(self):
        """Sync function returning non-Task/Future should NOT be detected."""
        code = "\nimport asyncio\ndef process():\n    return 42\n"
        tree = ast.parse(code)
        result = AsyncChecks.check_no_task_return_from_sync_cli(tree)
        assert result == []
