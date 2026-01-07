# src/mind/logic/engines/ast_gate/checks/async_checks.py
"""Async safety checks for constitutional enforcement."""

from __future__ import annotations

import ast

from mind.logic.engines.ast_gate.base import ASTHelpers


# ID: a6facc5a-b9b3-45fd-9ae9-414ca0976c6c
class AsyncChecks:
    """Async safety and event loop management checks."""

    @staticmethod
    # ID: 965336f9-45fd-4c4e-b063-1cba88974b3c
    def check_restricted_event_loop_creation(
        tree: ast.AST, forbidden_calls: list[str]
    ) -> list[str]:
        """
        Forbid dangerous event loop hijacking.

        ALLOWS (defensive patterns):
        - asyncio.get_event_loop() for checking state (not followed by .run_until_complete())
        - asyncio.run() when guarded by loop existence check

        FORBIDS (dangerous patterns):
        - asyncio.run() without checking for existing loop first
        - loop.run_until_complete() (manual loop hijacking)
        - asyncio.new_event_loop() (manual loop creation)
        """
        if not forbidden_calls:
            return []

        findings: list[str] = []

        # Build parent map for context analysis
        parent_map = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parent_map[child] = parent

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = ASTHelpers.full_attr_name(node.func)
            if not fn:
                continue

            # 1. CHECK: loop.run_until_complete() - ALWAYS DANGEROUS
            if fn.endswith(".run_until_complete"):
                findings.append(
                    f"Line {ASTHelpers.lineno(node)}: Forbidden manual loop hijacking '{fn}()'"
                )
                continue

            # 2. CHECK: asyncio.get_event_loop() - only dangerous if used for run_until_complete
            if ASTHelpers.matches_call(fn, ["asyncio.get_event_loop"]):
                # Check what they do with the loop
                if AsyncChecks._is_loop_hijacking(node, parent_map):
                    findings.append(
                        f"Line {ASTHelpers.lineno(node)}: Forbidden event-loop hijacking via get_event_loop().run_until_complete()"
                    )
                # Otherwise it's just checking - SAFE (defensive pattern)
                continue

            # 3. CHECK: asyncio.run() - only dangerous if NOT guarded
            if ASTHelpers.matches_call(fn, ["asyncio.run"]):
                # Check if this is in a defensive pattern
                if not AsyncChecks._is_defensively_guarded(node, tree, parent_map):
                    findings.append(
                        f"Line {ASTHelpers.lineno(node)}: Forbidden asyncio.run() without defensive loop check"
                    )
                # Otherwise it's guarded - SAFE (defensive pattern)
                continue

            # 4. CHECK: Other forbidden calls (asyncio.new_event_loop, etc.)
            if ASTHelpers.matches_call(fn, forbidden_calls):
                # These are always dangerous
                if fn not in [
                    "asyncio.get_event_loop",
                    "asyncio.run",
                ]:  # Already handled above
                    findings.append(
                        f"Line {ASTHelpers.lineno(node)}: Forbidden event-loop call '{fn}()'"
                    )

        return findings

    @staticmethod
    def _is_loop_hijacking(get_event_loop_call: ast.Call, parent_map: dict) -> bool:
        """
        Check if asyncio.get_event_loop() is followed by .run_until_complete().

        Pattern we're detecting:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(...)  # DANGEROUS
        """
        # Get the parent assignment or expression
        parent = parent_map.get(get_event_loop_call)

        # Check if assigned to a variable
        if isinstance(parent, ast.Assign):
            # Get the variable name
            if parent.targets and isinstance(parent.targets[0], ast.Name):
                loop_var = parent.targets[0].id

                # Look for usage of this variable with .run_until_complete()
                # We need to check the function/method body containing this assignment
                function_node = AsyncChecks._find_containing_function(
                    parent, parent_map
                )
                if function_node:
                    for node in ast.walk(function_node):
                        if isinstance(node, ast.Call):
                            if isinstance(node.func, ast.Attribute):
                                if (
                                    node.func.attr
                                    in ["run_until_complete", "run_forever"]
                                    and isinstance(node.func.value, ast.Name)
                                    and node.func.value.id == loop_var
                                ):
                                    return True

        # Check for direct chaining: asyncio.get_event_loop().run_until_complete(...)
        if isinstance(parent, ast.Attribute):
            if parent.attr in ["run_until_complete", "run_forever"]:
                return True

        return False

    @staticmethod
    def _is_defensively_guarded(
        asyncio_run_call: ast.Call, tree: ast.AST, parent_map: dict
    ) -> bool:
        """
        Check if asyncio.run() is guarded by a check for existing event loop.

        Defensive pattern we're allowing:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                # handle async context
            else:
                asyncio.run(...)  # SAFE - guarded
        """
        # Find the function containing this asyncio.run() call
        function_node = AsyncChecks._find_containing_function(
            asyncio_run_call, parent_map
        )
        if not function_node:
            # Top-level or script - always unguarded
            return False

        # Look for defensive patterns in the function:
        # 1. try/except with get_running_loop
        # 2. if statement checking loop.is_running()

        has_get_running_loop = False
        has_is_running_check = False

        for node in ast.walk(function_node):
            # Check for asyncio.get_running_loop() call
            if isinstance(node, ast.Call):
                fn = ASTHelpers.full_attr_name(node.func)
                if fn == "asyncio.get_running_loop":
                    has_get_running_loop = True

            # Check for .is_running() check
            if isinstance(node, ast.Attribute):
                if node.attr == "is_running":
                    has_is_running_check = True

        # If both defensive checks are present, it's guarded
        return has_get_running_loop and has_is_running_check

    @staticmethod
    def _find_containing_function(
        node: ast.AST, parent_map: dict
    ) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
        """Walk up the parent chain to find the containing function."""
        current = node
        while current in parent_map:
            current = parent_map[current]
            if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return current
        return None

    @staticmethod
    # ID: b6ae62b2-abe5-404a-a607-40095adb556e
    def check_no_import_time_async_singletons(
        tree: ast.AST, disallowed_calls: list[str]
    ) -> list[str]:
        """Forbid loop-bound async resource creation at module import time."""
        if not disallowed_calls:
            return []

        findings: list[str] = []
        for stmt in ASTHelpers.iter_module_level_stmts(tree):
            for node in ASTHelpers.walk_module_stmt_without_nested_scopes(stmt):
                if isinstance(node, ast.Call):
                    fn = ASTHelpers.full_attr_name(node.func)
                    if not fn:
                        continue
                    if ASTHelpers.matches_call(fn, disallowed_calls):
                        findings.append(
                            f"Line {ASTHelpers.lineno(node)}: Import-time async singleton creation: '{fn}()'"
                        )
        return findings

    @staticmethod
    # ID: ad987b5e-75c6-4e39-a44f-e349acf5fae2
    def check_no_module_level_async_engine(tree: ast.AST) -> list[str]:
        """Forbid module-level create_async_engine assignment."""
        findings: list[str] = []
        disallowed = [
            "create_async_engine",
            "sqlalchemy.ext.asyncio.create_async_engine",
        ]

        for stmt in ASTHelpers.iter_module_level_stmts(tree):
            value: ast.AST | None
            if isinstance(stmt, ast.Assign):
                value = stmt.value
            elif isinstance(stmt, ast.AnnAssign):
                value = stmt.value
            else:
                continue

            if value is None or not isinstance(value, ast.Call):
                continue

            fn = ASTHelpers.full_attr_name(value.func)
            if not fn:
                continue

            if ASTHelpers.matches_call(fn, disallowed):
                line = ASTHelpers.lineno(value)
                findings.append(
                    f"Line {line}: Module-level async engine creation is forbidden: '{fn}()'"
                )

        return findings

    @staticmethod
    # ID: 55f1eafc-a82d-4f56-90d8-fc40d7a6eb2e
    def check_no_task_return_from_sync_cli(tree: ast.AST) -> list[str]:
        """Forbid returning asyncio Tasks/Futures from sync functions."""
        findings: list[str] = []

        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue

            for inner in ast.walk(node):
                if not isinstance(inner, ast.Return):
                    continue
                if inner.value is None:
                    continue

                if isinstance(inner.value, ast.Call):
                    fn = ASTHelpers.full_attr_name(inner.value.func) or ""
                    leaf = fn.split(".")[-1]
                    if leaf == "create_task":
                        findings.append(
                            f"Line {ASTHelpers.lineno(inner)}: Sync function '{node.name}' returns Task"
                        )
                    elif leaf == "ensure_future":
                        findings.append(
                            f"Line {ASTHelpers.lineno(inner)}: Sync function '{node.name}' returns Future"
                        )

        return findings
