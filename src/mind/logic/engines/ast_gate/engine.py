# src/mind/logic/engines/ast_gate/engine.py
"""Main AST Gate Engine with constitutional check dispatch."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, ClassVar

# Note: GenericASTChecks will be the new module we create next
from mind.logic.engines.ast_gate.checks import (
    CapabilityChecks,
    GenericASTChecks,
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

    # Keep immutable to satisfy Ruff (RUF012) and to avoid accidental mutation.
    _SUPPORTED_CHECK_TYPES: ClassVar[frozenset[str]] = frozenset(
        {
            # Universal Primitives (New A2 logic to replace LLM usage)
            "generic_primitive",
            # Import checks (planned/partial in current engine)
            "import_boundary",
            "linter_compliance",
            # Async checks (planned/partial in current engine)
            "restrict_event_loop_creation",
            "no_import_time_async_singletons",
            "no_module_level_async_engine",
            "no_task_return_from_sync_cli",
            # Logging checks
            "no_print_statements",
            # Naming checks (planned/partial in current engine)
            "cli_async_helpers_private",
            "test_file_naming",
            "max_file_lines",
            "max_function_length",  # NEW: Function length checking
            # Purity checks
            "stable_id_anchor",
            "forbidden_decorators",
            "forbidden_primitives",
            "required_decorator",
            "decorator_args",
            # Capability checks
            "capability_assignment",
        }
    )

    @classmethod
    # ID: c8e4be5d-60c7-481e-886d-2091a5206195
    def supported_check_types(cls) -> set[str]:
        """
        Declares supported Constitution-driven AST checks.
        Governance planners use this to determine rule coverage.
        """
        return set(cls._SUPPORTED_CHECK_TYPES)

    # ID: 9e64f392-e30d-44bb-ac4d-c8b2b32723d1
    def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        """
        Verify file against constitutional rules via AST analysis.

        Args:
            file_path: Absolute path to Python file
            params: Check parameters including check_type

        Returns:
            EngineResult with violations if any found
        """
        check_type = str(params.get("check_type") or "").strip()
        if not check_type:
            return EngineResult(
                ok=False,
                message="Logic Error: Missing ast_gate check_type",
                violations=["Internal: no check_type provided"],
                engine_id=self.engine_id,
            )

        if check_type not in self._SUPPORTED_CHECK_TYPES:
            return EngineResult(
                ok=False,
                message=f"Logic Error: Unknown ast_gate check_type '{check_type}'",
                violations=[],
                engine_id=self.engine_id,
            )

        try:
            source = file_path.read_text(encoding="utf-8")
            source_lines = source.splitlines()
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError as e:
            return EngineResult(
                ok=False,
                message=f"Syntax Error in source: {e}",
                violations=[],
                engine_id=self.engine_id,
            )
        except OSError as e:
            return EngineResult(
                ok=False,
                message=f"IO Error reading source: {e}",
                violations=[],
                engine_id=self.engine_id,
            )

        violations: list[str] = []

        # --- New Universal Primitive Logic ---
        if check_type == "generic_primitive":
            selector = params.get("selector", {})
            requirement = params.get("requirement", {})

            for node in ast.walk(tree):
                # We only want to check functional blocks like Classes or Functions
                if not isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                ):
                    continue

                # 1. Selection: Does this specific rule apply to this function/class?
                if GenericASTChecks.is_selected(node, selector):
                    # 2. Validation: Does it meet the requirement (e.g. correct return type)?
                    error = GenericASTChecks.validate_requirement(node, requirement)
                    if error:
                        violations.append(f"Line {node.lineno}: '{node.name}' {error}")

        # --- Existing Deterministic Dispatches ---
        elif check_type == "capability_assignment":
            violations.extend(
                CapabilityChecks.check_capability_assignment(tree, file_path=file_path)
            )
        elif check_type == "stable_id_anchor":
            violations.extend(PurityChecks.check_stable_id_anchor(source))
        elif check_type == "forbidden_decorators":
            forbidden = params.get("forbidden", []) or params.get("decorators", [])
            violations.extend(PurityChecks.check_forbidden_decorators(tree, forbidden))
        elif check_type == "forbidden_primitives":
            forbidden = params.get("forbidden", []) or params.get("primitives", [])
            violations.extend(PurityChecks.check_forbidden_primitives(tree, forbidden))
        elif check_type == "no_print_statements":
            violations.extend(PurityChecks.check_no_print_statements(tree))
        elif check_type == "required_decorator":
            decorator = str(
                params.get("target") or params.get("decorator") or ""
            ).strip()
            if not decorator:
                violations.append(
                    "Internal: required_decorator missing 'target'/'decorator' param."
                )
            else:
                violations.extend(
                    PurityChecks.check_required_decorator(
                        tree=tree,
                        decorator=decorator,
                        only_public=bool(params.get("only_public", True)),
                        ignore_tests=bool(params.get("ignore_tests", True)),
                    )
                )
        elif check_type == "decorator_args":
            decorator = str(params.get("decorator") or "").strip()
            required_args = params.get("required_args") or []
            if not decorator:
                violations.append("Internal: decorator_args missing 'decorator' param.")
            elif not isinstance(required_args, list) or not all(
                isinstance(x, str) for x in required_args
            ):
                violations.append(
                    "Internal: decorator_args requires 'required_args' as list[str]."
                )
            else:
                violations.extend(
                    PurityChecks.check_decorator_args(
                        tree=tree,
                        decorator=decorator,
                        required_args=required_args,
                    )
                )
        # NEW: Function length checking
        elif check_type == "max_function_length":
            limit = int(params.get("limit", 50))
            violations.extend(NamingChecks.check_max_function_length(tree, limit=limit))
        else:
            # Supported but not yet implemented in this engine version (by design).
            return EngineResult(
                ok=False,
                message=f"Coverage Gap: ast_gate check_type '{check_type}' declared but not yet implemented.",
                violations=[],
                engine_id=self.engine_id,
            )

        if not violations:
            return EngineResult(
                ok=True,
                message="AST Gate: No constitutional violations detected.",
                violations=[],
                engine_id=self.engine_id,
            )

        return EngineResult(
            ok=False,
            message="AST Gate: Constitutional violations detected.",
            violations=violations,
            engine_id=self.engine_id,
        )
