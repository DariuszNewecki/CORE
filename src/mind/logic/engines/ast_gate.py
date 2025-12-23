# src/mind/logic/engines/ast_gate.py
"""
ASTGateEngine is the deterministic (non-LLM) enforcement engine for rules that
can be verified via Python AST inspection.

Design goals:
- Support dynamic dispatch via params["check_type"] (Constitution-driven).
- Provide robust, explainable violations with line numbers.
- Preserve backward compatibility with existing params such as:
  - forbidden_calls / patterns_prohibited
  - forbidden_decorators
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .base import BaseEngine, EngineResult


# ID: 220fb48b-603c-4d67-8219-39eab846e8a7
class ASTGateEngine(BaseEngine):
    """
    Fact-Based Syntax Tree Auditor.
    Scans Python source code for logical violations defined in the Constitution.
    """

    engine_id = "ast_gate"

    # ID: 7b7a7e34-2df1-4f60-9f7c-98e81f8dfd2a
    @classmethod
    # ID: 0e3ad812-94d4-42c8-9eac-2d4bc4104900
    def supported_check_types(cls) -> set[str]:
        """
        Declares the supported Constitution-driven AST checks.

        Governance coverage and audit planners can use this to determine whether
        an ast_gate rule is implementable.
        """
        return {
            "import_boundary",
            "restrict_event_loop_creation",
            "no_import_time_async_singletons",
            "no_module_level_async_engine",
            "no_task_return_from_sync_cli",
        }

    # ID: 874d9dbc-e012-4a22-8fc0-3738b85c6984
    def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        violations: list[str] = []

        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError as e:
            return EngineResult(
                ok=False,
                message=f"Syntax Error in source: {e}",
                violations=[],
                engine_id=self.engine_id,
            )

        check_type = params.get("check_type")
        if isinstance(check_type, str) and check_type.strip():
            violations.extend(self._dispatch_check(tree, check_type.strip(), params))
        else:
            # Backward compatible behavior:
            # 1) forbidden_calls (eval, exec, subprocess patterns, etc.)
            forbidden_calls = params.get("forbidden_calls") or params.get(
                "patterns_prohibited", []
            )
            if forbidden_calls:
                violations.extend(self._check_calls(tree, forbidden_calls))

            # 2) subprocess shell=True
            if "subprocess" in str(forbidden_calls):
                violations.extend(self._check_subprocess_shell(tree))

            # 3) forbidden decorators
            forbidden_decorators = params.get("forbidden_decorators", [])
            if forbidden_decorators:
                violations.extend(self._check_decorators(tree, forbidden_decorators))

        if not violations:
            return EngineResult(
                ok=True,
                message="Constitutional adherence verified.",
                violations=[],
                engine_id=self.engine_id,
            )

        return EngineResult(
            ok=False,
            message=(
                f"Constitutional Violation: {len(violations)} restricted logical "
                "structures found."
            ),
            violations=violations,
            engine_id=self.engine_id,
        )

    # -------------------------
    # Check-type dispatcher
    # -------------------------

    def _dispatch_check(
        self, tree: ast.AST, check_type: str, params: dict[str, Any]
    ) -> list[str]:
        match check_type:
            case "import_boundary":
                forbidden_imports = params.get("forbidden_imports", [])
                return self._check_forbidden_imports(tree, forbidden_imports)

            case "restrict_event_loop_creation":
                forbidden_calls = params.get("forbidden_calls", [])
                return self._check_restricted_event_loop_creation(tree, forbidden_calls)

            case "no_import_time_async_singletons":
                disallowed_calls = params.get("disallowed_calls", [])
                return self._check_no_import_time_async_singletons(
                    tree, disallowed_calls
                )

            case "no_module_level_async_engine":
                return self._check_no_module_level_async_engine(tree)

            case "no_task_return_from_sync_cli":
                return self._check_no_task_return_from_sync_cli(tree)

            case _:
                return [
                    (
                        f"Unknown ast_gate check_type '{check_type}'. "
                        "This rule is not enforceable until a corresponding AST check is implemented."
                    )
                ]

    # -------------------------
    # Common helpers
    # -------------------------

    def _iter_module_level_stmts(self, tree: ast.AST) -> Iterable[ast.stmt]:
        if isinstance(tree, ast.Module):
            return tree.body
        return []

    def _lineno(self, node: ast.AST) -> int:
        return int(getattr(node, "lineno", 0) or 0)

    def _full_attr_name(self, node: ast.AST) -> str | None:
        """
        Attempt to resolve a dotted name from ast.Name / ast.Attribute chains.

        Examples:
            asyncio.run  -> "asyncio.run"
            loop.create_task -> "loop.create_task"   (best-effort)
            create_async_engine -> "create_async_engine"
        """
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            left = self._full_attr_name(node.value)
            if left:
                return f"{left}.{node.attr}"
            return node.attr
        return None

    def _matches_call(self, call_name: str, disallowed: list[str]) -> bool:
        """
        Match strategy:
        - Exact match on fully qualified name
        - Exact match on leaf name (last segment)
        - Suffix match (e.g., endswith ".create_async_engine")
        """
        leaf = call_name.split(".")[-1]
        for item in disallowed:
            if call_name == item:
                return True
            if leaf == item:
                return True
            if item.startswith(".") and call_name.endswith(item):
                return True
            if item.endswith(f".{leaf}") and call_name.endswith(f".{leaf}"):
                return True
        return False

    def _walk_module_stmt_without_nested_scopes(
        self, stmt: ast.stmt
    ) -> Iterable[ast.AST]:
        """
        Walk a module-level statement but do not descend into nested scopes
        (function defs, class defs, lambdas).
        """

        def _walk(node: ast.AST) -> Iterable[ast.AST]:
            yield node
            for child in ast.iter_child_nodes(node):
                if isinstance(
                    child,
                    (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda),
                ):
                    continue
                yield from _walk(child)

        return _walk(stmt)

    # -------------------------
    # Existing checks (back-compat)
    # -------------------------

    def _check_calls(self, tree: ast.AST, forbidden: list[str]) -> list[str]:
        findings: list[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            # Handle direct calls: eval()
            if isinstance(node.func, ast.Name) and node.func.id in forbidden:
                findings.append(
                    f"Line {self._lineno(node)}: Forbidden primitive call '{node.func.id}()'"
                )
                continue

            # Handle attribute calls: os.system()
            if isinstance(node.func, ast.Attribute) and node.func.attr in forbidden:
                findings.append(
                    f"Line {self._lineno(node)}: Forbidden attribute call '.{node.func.attr}()'"
                )

        return findings

    def _check_subprocess_shell(self, tree: ast.AST) -> list[str]:
        findings: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                for keyword in node.keywords:
                    if (
                        keyword.arg == "shell"
                        and isinstance(keyword.value, ast.Constant)
                        and keyword.value.value is True
                    ):
                        findings.append(
                            f"Line {self._lineno(node)}: Security Risk: Execution with shell=True detected."
                        )
        return findings

    def _check_decorators(self, tree: ast.AST, forbidden: list[str]) -> list[str]:
        findings: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                for dec in node.decorator_list:
                    if isinstance(dec, ast.Name) and dec.id in forbidden:
                        findings.append(
                            f"Line {self._lineno(node)}: Purity Violation: Forbidden decorator '@{dec.id}' (Move to DB)"
                        )
                    elif (
                        isinstance(dec, ast.Call)
                        and isinstance(dec.func, ast.Name)
                        and dec.func.id in forbidden
                    ):
                        findings.append(
                            f"Line {self._lineno(node)}: Purity Violation: Forbidden decorator '@{dec.func.id}' (Move to DB)"
                        )
        return findings

    # -------------------------
    # New enforceable check_types
    # -------------------------

    def _check_forbidden_imports(
        self, tree: ast.AST, forbidden: list[str]
    ) -> list[str]:
        """
        Enforces policy rule 'import_boundary' using 'forbidden_imports' list.

        forbidden_imports entries are expected as strings like:
          - "shared.infrastructure.database.session_manager.get_session"
        """
        if not forbidden:
            return []

        findings: list[str] = []
        forbidden_set = set(forbidden)

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                for alias in node.names:
                    imported = alias.name
                    fq = f"{mod}.{imported}" if mod else imported
                    if fq in forbidden_set:
                        findings.append(
                            f"Line {self._lineno(node)}: Forbidden import-from '{fq}'"
                        )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    mod = alias.name
                    if mod in forbidden_set:
                        findings.append(
                            f"Line {self._lineno(node)}: Forbidden import '{mod}'"
                        )

        return findings

    def _check_restricted_event_loop_creation(
        self, tree: ast.AST, forbidden_calls: list[str]
    ) -> list[str]:
        """Enforces rule: asyncio loop creation/management must be restricted."""
        if not forbidden_calls:
            return []

        findings: list[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = self._full_attr_name(node.func)
            if not fn:
                continue

            if fn.endswith(".run_until_complete") and self._matches_call(
                "loop.run_until_complete", forbidden_calls
            ):
                findings.append(
                    f"Line {self._lineno(node)}: Forbidden event-loop call '{fn}()'"
                )
                continue

            if self._matches_call(fn, forbidden_calls):
                findings.append(
                    f"Line {self._lineno(node)}: Forbidden event-loop call '{fn}()'"
                )

        return findings

    def _check_no_import_time_async_singletons(
        self, tree: ast.AST, disallowed_calls: list[str]
    ) -> list[str]:
        """Forbids loop-bound async resource creation at module import time."""
        if not disallowed_calls:
            return []

        findings: list[str] = []
        for stmt in self._iter_module_level_stmts(tree):
            for node in self._walk_module_stmt_without_nested_scopes(stmt):
                if isinstance(node, ast.Call):
                    fn = self._full_attr_name(node.func)
                    if not fn:
                        continue
                    if self._matches_call(fn, disallowed_calls):
                        findings.append(
                            f"Line {self._lineno(node)}: Import-time async singleton creation detected: '{fn}()'"
                        )
        return findings

    def _check_no_module_level_async_engine(self, tree: ast.AST) -> list[str]:
        """Forbid module-level create_async_engine assignment."""
        findings: list[str] = []
        disallowed = [
            "create_async_engine",
            "sqlalchemy.ext.asyncio.create_async_engine",
        ]

        for stmt in self._iter_module_level_stmts(tree):
            value: ast.AST | None
            if isinstance(stmt, ast.Assign):
                value = stmt.value
            elif isinstance(stmt, ast.AnnAssign):
                value = stmt.value
            else:
                continue

            if value is None or not isinstance(value, ast.Call):
                continue

            fn = self._full_attr_name(value.func)
            if not fn:
                continue

            if self._matches_call(fn, disallowed):
                line = self._lineno(value)
                findings.append(
                    f"Line {line}: Module-level async engine creation is forbidden: '{fn}()'. "
                    "Engines/pools must be created lazily inside the active event loop/runtime scope."
                )

        return findings

    def _check_no_task_return_from_sync_cli(self, tree: ast.AST) -> list[str]:
        """Forbids returning asyncio Tasks/Futures from sync (non-async) functions."""
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
                    fn = self._full_attr_name(inner.value.func) or ""
                    leaf = fn.split(".")[-1]
                    if leaf == "create_task":
                        findings.append(
                            f"Line {self._lineno(inner)}: Sync function '{node.name}' returns a Task via '{fn}()' "
                            "(forbidden for CLI sync entrypoints)."
                        )
                    elif leaf == "ensure_future":
                        findings.append(
                            f"Line {self._lineno(inner)}: Sync function '{node.name}' returns a Future/Task via '{fn}()' "
                            "(forbidden for CLI sync entrypoints)."
                        )

        return findings
