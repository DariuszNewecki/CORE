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
        """Forbid manual event loop creation/management."""
        if not forbidden_calls:
            return []

        findings: list[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = ASTHelpers.full_attr_name(node.func)
            if not fn:
                continue

            if fn.endswith(".run_until_complete") and ASTHelpers.matches_call(
                "loop.run_until_complete", forbidden_calls
            ):
                findings.append(
                    f"Line {ASTHelpers.lineno(node)}: Forbidden event-loop call '{fn}()'"
                )
                continue

            if ASTHelpers.matches_call(fn, forbidden_calls):
                findings.append(
                    f"Line {ASTHelpers.lineno(node)}: Forbidden event-loop call '{fn}()'"
                )

        return findings

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
