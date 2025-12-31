# src/mind/logic/engines/ast_gate/engine.py
"""
Main AST Gate Engine with constitutional check dispatch.

REFACTORED:
- Full support for all 19 deterministic check types.
- Aligned with 'body_contracts.json' for headless execution.
- Optimized dispatcher to minimize LLM usage.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, ClassVar

from mind.logic.engines.ast_gate.checks import (
    AsyncChecks,
    CapabilityChecks,
    GenericASTChecks,
    ImportChecks,
    NamingChecks,
    PurityChecks,
)
from mind.logic.engines.base import BaseEngine, EngineResult


# ID: f5f18c87-adf8-4ba3-b3c6-e2d90d1f85a4
class ASTGateEngine(BaseEngine):
    """
    Fact-Based Syntax Tree Auditor.
    Scans Python source code for constitutional violations via AST inspection.
    """

    engine_id = "ast_gate"

    _SUPPORTED_CHECK_TYPES: ClassVar[frozenset[str]] = frozenset(
        {
            "generic_primitive",
            "import_boundary",
            "linter_compliance",
            "restrict_event_loop_creation",
            "no_import_time_async_singletons",
            "no_module_level_async_engine",
            "no_task_return_from_sync_cli",
            "no_print_statements",
            "cli_async_helpers_private",
            "test_file_naming",
            "max_file_lines",
            "max_function_length",
            "stable_id_anchor",
            "id_anchor",
            "forbidden_decorators",
            "forbidden_primitives",
            "forbidden_assignments",
            "write_defaults_false",
            "required_decorator",
            "decorator_args",
            "capability_assignment",
        }
    )

    @classmethod
    # ID: 7b10eec7-63a6-4c54-82c9-8b961f976cce
    def supported_check_types(cls) -> set[str]:
        return set(cls._SUPPORTED_CHECK_TYPES)

    # ID: b2f28048-fa49-4430-a025-c35d30d8c88f
    def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        check_type = str(params.get("check_type") or "").strip()

        if not check_type or check_type not in self._SUPPORTED_CHECK_TYPES:
            return EngineResult(
                ok=False,
                message=f"Logic Error: Unknown check_type '{check_type}'",
                violations=[],
                engine_id=self.engine_id,
            )

        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(file_path))
        except Exception as e:
            return EngineResult(
                ok=False,
                message=f"Parse Error: {e}",
                violations=[],
                engine_id=self.engine_id,
            )

        violations: list[str] = []

        # 1. CORE DISPATCHER
        if check_type == "generic_primitive":
            selector = params.get("selector", {})
            requirement = params.get("requirement", {})
            for node in ast.walk(tree):
                if isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                ):
                    if GenericASTChecks.is_selected(node, selector):
                        error = GenericASTChecks.validate_requirement(node, requirement)
                        if error:
                            violations.append(
                                f"Line {node.lineno}: '{node.name}' {error}"
                            )

        # 2. IMPORT & LINTING
        elif check_type == "import_boundary":
            violations.extend(
                ImportChecks.check_forbidden_imports(tree, params.get("forbidden", []))
            )
        elif check_type == "linter_compliance":
            violations.extend(ImportChecks.check_import_order(tree, params))

        # 3. ASYNC SAFETY
        elif check_type == "restrict_event_loop_creation":
            violations.extend(
                AsyncChecks.check_restricted_event_loop_creation(
                    tree, params.get("forbidden_calls", [])
                )
            )
        elif check_type == "no_import_time_async_singletons":
            violations.extend(
                AsyncChecks.check_no_import_time_async_singletons(
                    tree, params.get("disallowed_calls", [])
                )
            )
        elif check_type == "no_module_level_async_engine":
            violations.extend(AsyncChecks.check_no_module_level_async_engine(tree))
        elif check_type == "no_task_return_from_sync_cli":
            violations.extend(AsyncChecks.check_no_task_return_from_sync_cli(tree))

        # 4. PURITY & LOGGING
        elif check_type == "no_print_statements":
            violations.extend(PurityChecks.check_no_print_statements(tree))
        elif check_type in ("stable_id_anchor", "id_anchor"):
            violations.extend(PurityChecks.check_stable_id_anchor(source))
        elif check_type == "forbidden_decorators":
            violations.extend(
                PurityChecks.check_forbidden_decorators(
                    tree, params.get("forbidden", [])
                )
            )
        elif check_type == "forbidden_primitives":
            violations.extend(
                PurityChecks.check_forbidden_primitives(
                    tree,
                    params.get("forbidden", []),
                    file_path,
                    params.get("allowed_domains", []),
                )
            )
        elif check_type == "forbidden_assignments":
            targets = params.get("targets", [])
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for t in node.targets:
                        if isinstance(t, ast.Name) and t.id in targets:
                            violations.append(
                                f"Line {node.lineno}: Forbidden hardcoded assignment to '{t.id}'"
                            )

        # 5. BODY CONTRACTS (SAFE BY DEFAULT)
        elif check_type == "write_defaults_false":
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for arg, default in zip(
                        reversed(node.args.args), reversed(node.args.defaults)
                    ):
                        if (
                            arg.arg == "write"
                            and isinstance(default, ast.Constant)
                            and default.value is True
                        ):
                            violations.append(
                                f"Line {node.lineno}: Parameter 'write' must default to False"
                            )

        # 6. NAMING & METADATA
        elif check_type == "cli_async_helpers_private":
            violations.extend(NamingChecks.check_cli_async_helpers_private(tree))
        elif check_type == "test_file_naming":
            violations.extend(NamingChecks.check_test_file_naming(str(file_path)))
        elif check_type == "max_file_lines":
            violations.extend(
                NamingChecks.check_max_file_lines(
                    tree, str(file_path), params.get("limit", 400)
                )
            )
        elif check_type == "max_function_length":
            violations.extend(
                NamingChecks.check_max_function_length(
                    tree, limit=params.get("limit", 50)
                )
            )
        elif check_type == "capability_assignment":
            violations.extend(
                CapabilityChecks.check_capability_assignment(tree, file_path=file_path)
            )
        elif check_type == "required_decorator":
            decorator = str(
                params.get("target") or params.get("decorator") or ""
            ).strip()
            if decorator:
                # FIXED: Extract and pass exclude_patterns and exclude_decorators
                exclude_patterns = params.get("exclude_patterns", [])
                exclude_decorators = params.get("exclude_decorators", [])

                violations.extend(
                    PurityChecks.check_required_decorator(
                        tree,
                        decorator,
                        exclude_patterns=exclude_patterns,
                        exclude_decorators=exclude_decorators,
                    )
                )
        elif check_type == "decorator_args":
            decorator = str(params.get("decorator") or "").strip()
            args = params.get("required_args", [])
            if decorator:
                violations.extend(
                    PurityChecks.check_decorator_args(tree, decorator, args)
                )

        return EngineResult(
            ok=(len(violations) == 0),
            message=(
                "AST Gate: Compliant"
                if not violations
                else "AST Gate: Violations found"
            ),
            violations=violations,
            engine_id=self.engine_id,
        )
