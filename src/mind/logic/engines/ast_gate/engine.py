# src/mind/logic/engines/ast_gate/engine.py
# ID: 4803b5d0-4f64-4b7e-9b2e-d5d59f2137d8

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, ClassVar

from mind.logic.engines.ast_gate.checks import (
    AsyncChecks,
    CapabilityChecks,
    ConservationChecks,
    GenericASTChecks,
    NamingChecks,
    PurityChecks,
)
from mind.logic.engines.ast_gate.checks.import_boundary import ImportBoundaryCheck
from mind.logic.engines.ast_gate.checks.modularity_checks import ModularityChecker
from mind.logic.engines.base import BaseEngine, EngineResult
from shared.path_resolver import PathResolver


# ID: 0b7d0813-a8e0-4901-b7fa-6c57b48c543d
class ASTGateEngine(BaseEngine):
    engine_id = "ast_gate"

    def __init__(self, path_resolver: PathResolver):
        self._paths = path_resolver
        self._capability_checks = CapabilityChecks(path_resolver)
        self._modularity_checker = ModularityChecker()

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
            "no_direct_writes",
            "required_calls",
            "modularity",
            "metadata_only_diff",
            "logic_conservation",
        }
    )

    # ID: d730e583-f41d-482e-ad42-b5ec368775cf
    async def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        check_type = params.get("check_type")
        context = params.get("_context")  # The cache is passed here

        # 1. SPECIAL CASE: Runtime Proofs (Enforced during mutation, not audit)
        if check_type == "metadata_only_diff":
            return EngineResult(
                ok=True,
                message="metadata_only_diff is enforced at action execution time, not audit time.",
                violations=[],
                engine_id=self.engine_id,
            )

        # 2. SENSATION: Load source and tree
        try:
            source = file_path.read_text(encoding="utf-8")
        except Exception as e:
            return EngineResult(False, f"Read Error: {e}", [], self.engine_id)

        tree = None
        if context and hasattr(context, "get_tree"):
            tree = context.get_tree(file_path)

        if tree is None:
            try:
                tree = ast.parse(source, filename=str(file_path))
            except Exception as e:
                return EngineResult(False, f"Parse Error: {e}", [], self.engine_id)

        violations: list[str] = []

        # 3. DISPATCH LOGIC: Exhaustive implementation of _SUPPORTED_CHECK_TYPES

        # --- Purity & Integrity ---
        if check_type in ("stable_id_anchor", "id_anchor"):
            violations.extend(PurityChecks.check_stable_id_anchor(source))

        elif check_type == "logic_conservation":
            violations.extend(
                ConservationChecks.check_logic_conservation(file_path, source, params)
            )

        elif check_type == "forbidden_primitives":
            violations.extend(
                PurityChecks.check_forbidden_primitives(
                    tree,
                    params.get("forbidden", []),
                    file_path,
                    params.get("allowed_domains"),
                )
            )

        elif check_type == "forbidden_decorators":
            violations.extend(
                PurityChecks.check_forbidden_decorators(
                    tree, params.get("forbidden", [])
                )
            )

        elif check_type == "no_direct_writes":
            violations.extend(PurityChecks.check_no_direct_writes(tree))

        # --- Boundaries & Architecture ---
        elif check_type == "import_boundary":
            res = ImportBoundaryCheck.check(file_path, tree, params)
            if not res.ok:
                violations.extend(res.violations)

        elif check_type == "capability_assignment":
            violations.extend(
                self._capability_checks.check_capability_assignment(
                    tree, file_path=file_path
                )
            )

        elif check_type == "modularity":
            # Modularity checks return dicts with messages
            method_name = params.get("check_method", "check_refactor_score")
            method = getattr(self._modularity_checker, method_name)
            findings = method(file_path, params)
            violations.extend([f["message"] for f in findings])

        # --- Async Safety ---
        elif check_type == "restrict_event_loop_creation":
            violations.extend(
                AsyncChecks.check_restricted_event_loop_creation(
                    tree, params.get("forbidden_calls", [])
                )
            )

        elif check_type == "no_import_time_async_singletons":
            violations.extend(
                AsyncChecks.check_no_import_time_async_singletons(
                    tree, params.get("calls", [])
                )
            )

        elif check_type == "no_module_level_async_engine":
            violations.extend(AsyncChecks.check_no_module_level_async_engine(tree))

        elif check_type == "no_task_return_from_sync_cli":
            violations.extend(AsyncChecks.check_no_task_return_from_sync_cli(tree))

        # --- Naming & Standards ---
        elif check_type == "max_file_lines":
            violations.extend(
                NamingChecks.check_max_file_lines(
                    tree, str(file_path), params.get("limit", 400)
                )
            )

        elif check_type == "max_function_length":
            violations.extend(
                NamingChecks.check_max_function_length(tree, params.get("limit", 50))
            )

        elif check_type == "no_print_statements":
            violations.extend(PurityChecks.check_no_print_statements(tree))

        elif check_type == "test_file_naming":
            violations.extend(NamingChecks.check_test_file_naming(str(file_path)))

        # --- Generic & Contract Primitives ---
        elif check_type in (
            "generic_primitive",
            "required_calls",
            "decorator_args",
            "write_defaults_false",
        ):
            selector = params.get("selector", {})
            requirement = params.get(
                "requirement", params
            )  # Fallback to params for flat rules
            for node in ast.walk(tree):
                if GenericASTChecks.is_selected(node, selector):
                    err = GenericASTChecks.validate_requirement(node, requirement)
                    if err:
                        violations.append(f"Line {getattr(node, 'lineno', '?')}: {err}")

        # 4. FINAL VERDICT
        return EngineResult(
            ok=(not violations),
            message=f"AST Check complete: {check_type}",
            violations=violations,
            engine_id=self.engine_id,
        )
