# src/mind/logic/engines/ast_gate/engine.py

from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from mind.logic.engines.ast_gate.checks import (
    AsyncChecks,
    AwaitingReauditChecks,
    CapabilityChecks,
    ConservationChecks,
    GenericASTChecks,
    ImportChecks,
    IndeterminateHumanChecks,
    LoggingChecks,
    NamingChecks,
    PromptModelChecks,
    PurityChecks,
    SchemaConformanceChecks,
)
from mind.logic.engines.ast_gate.checks.api_auth_checks import ApiAuthChecks
from mind.logic.engines.ast_gate.checks.artifact_discovery_check import (
    ArtifactDiscoveryCheck,
)
from mind.logic.engines.ast_gate.checks.duplicate_ids_check import (
    check_duplicate_ids,
)
from mind.logic.engines.ast_gate.checks.modularity_checks import ModularityChecker
from mind.logic.engines.ast_gate.checks.protected_namespace_access_check import (
    ProtectedNamespaceAccessCheck,
)
from mind.logic.engines.ast_gate.checks.runtime_import_boundary import (
    RuntimeImportBoundaryCheck,
)
from mind.logic.engines.ast_gate.checks.test_gen_acceptance_check import (
    TestGenAcceptanceCheck,
)
from mind.logic.engines.base import BaseEngine, EngineResult, EvidenceClass
from shared.infrastructure.intent.filesystem_operations import (
    FsOperationTaxonomy,
    load_filesystem_operations,
)
from shared.models import AuditFinding, AuditSeverity
from shared.path_resolver import PathResolver


if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext


# ID: 0b7d0813-a8e0-4901-b7fa-6c57b48c543d
class ASTGateEngine(BaseEngine):
    engine_id = "ast_gate"
    evidence_class = EvidenceClass.PROVEN  # ADR-113: deterministic verdict

    def __init__(self, path_resolver: PathResolver):
        self._paths = path_resolver
        self._capability_checks = CapabilityChecks(path_resolver)
        self._modularity_checker = ModularityChecker()
        self._fs_taxonomy: FsOperationTaxonomy | None = None

    @property
    # ID: a8436363-71f5-4ae5-b698-cdc1593cc6c8
    def fs_taxonomy(self) -> FsOperationTaxonomy:
        """Lazily-loaded filesystem-operation taxonomy (ADR-077 §6 step 3, #489).

        Sole consumer point for the taxonomy inside the AST gate. Fail-closed:
        a loader error surfaces as an engine-load failure on first audit
        cycle that exercises a taxonomy-reading check (currently
        ``no_direct_writes``). Cached after first load — the taxonomy is
        constitutional and does not change at runtime.
        """
        if self._fs_taxonomy is None:
            self._fs_taxonomy = load_filesystem_operations()
        return self._fs_taxonomy

    # Every check_type listed here MUST have a matching dispatch clause in
    # ``verify()``. The unknown-check_type guard at the end of verify()
    # surfaces any drift between this set and the dispatch chain — keep
    # them aligned. Two aliases (``decorator_args``, ``required_calls``)
    # route through the ``generic_primitive`` harness with ``selector`` +
    # ``requirement`` params; the rest are first-class entries with their own
    # clauses.
    #
    # ``write_defaults_false`` was a third alias and is retired (#820
    # follow-up). It was declared here and routed to the harness, but
    # ``GenericASTChecks.validate_requirement`` has no branch for it, so it
    # validated nothing on every input — a capability the vocabulary
    # advertised and did not have. Declaring it was worse than omitting it:
    # dispatch succeeded, so neither the unsupported-check_type contract nor
    # the empty-violations contract could see it. The real obligation is
    # enforced by ``action_pattern`` (and, on the Body contracts surface, by
    # body_contracts_service's own `write_defaults_false` rule — a different
    # namespace, untouched here). No enforcement mapping referenced the alias.
    _SUPPORTED_CHECK_TYPES: ClassVar[frozenset[str]] = frozenset(
        {
            "generic_primitive",
            "runtime_import_boundary",
            "restrict_event_loop_creation",
            "no_import_time_async_singletons",
            "no_module_level_async_engine",
            "no_task_return_from_sync_cli",
            "no_print_statements",
            "test_file_naming",
            "max_file_lines",
            "max_function_length",
            "stable_id_anchor",
            "id_anchor",
            "duplicate_ids",
            "docstrings_present",
            "forbidden_decorators",
            "forbidden_primitives",
            "forbidden_assignments",
            "forbidden_imports_and_calls",
            "prompt_model_required",
            "required_decorator",
            "action_pattern",
            "decorator_args",
            "capability_assignment",
            "no_direct_writes",
            "required_calls",
            "modularity",
            "metadata_only_diff",
            "logic_conservation",
            "logger_not_presentation",
            "protected_namespace_access",
            "artifact_discovery_through_registry",
            "test_gen_acceptance_includes_pytest_gate",
            "import_order",
            "module_header",
            "schema_conformance",
            "tempfile_default_dir",
            "reaudit_requires_reaudit_mechanism",
            "indeterminate_requires_human_mechanism",
            "future_annotations",
            "type_annotations",
            "router_exposure_enforcement",
            "route_module_must_declare_exposure",
            "sensitive_route_must_be_gated",
        }
    )

    # duplicate_ids is corpus-level (it must see every file at once to detect
    # a UUID collision), so it dispatches through verify_context, not the
    # per-file verify() below. BaseEngine.is_context_level_for consults this.
    _context_check_types: ClassVar[frozenset[str]] = frozenset({"duplicate_ids"})

    # ID: e2e5faff-20e7-48a0-ad44-5ef2720d2104
    async def verify_context(
        self, context: AuditorContext, params: dict[str, Any]
    ) -> list[AuditFinding]:
        """Corpus-level dispatch. Only ``duplicate_ids`` is context-level for
        ast_gate; every other check_type routes per-file through verify()."""
        check_type = params.get("check_type")
        if check_type == "duplicate_ids":
            return check_duplicate_ids(context, params)
        return [
            AuditFinding(
                check_id=f"{self.engine_id}.error",
                severity=AuditSeverity.BLOCK,
                message=(
                    f"{self.engine_id}.verify_context received non-context-level "
                    f"check_type {check_type!r}; per-file check_types route through "
                    "verify(file_path, ...)."
                ),
                file_path="none",
            )
        ]

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

        violations: list[str | dict[str, Any]] = []

        # 3. DISPATCH LOGIC: Exhaustive implementation of _SUPPORTED_CHECK_TYPES

        # --- Purity & Integrity ---
        if check_type in ("stable_id_anchor", "id_anchor"):
            violations.extend(PurityChecks.check_stable_id_anchor(source))

        elif check_type == "docstrings_present":
            violations.extend(PurityChecks.check_docstrings_present(tree))

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

        elif check_type == "forbidden_assignments":
            # data.ssot.database_primacy: flag module-level constants that
            # belong in the database SSOT (LLM_MODELS, AGENT_ROLES, ...).
            violations.extend(
                PurityChecks.check_forbidden_assignments(
                    tree, params.get("targets", [])
                )
            )

        elif check_type == "required_decorator":
            # Wired here for the first time; the check exists on
            # PurityChecks but had no dispatcher before #588.
            decorator = params.get("required_decorator") or params.get("decorator")
            if decorator:
                violations.extend(
                    PurityChecks.check_required_decorator(
                        tree, decorator=decorator, file_path=file_path
                    )
                )

        elif check_type == "action_pattern":
            # #820: dispatched here for the first time. The mapping named
            # this check_type from the start; no clause existed, so the
            # unknown-check_type guard below returned ok=False with an
            # empty violation list — which rule_executor then swallowed,
            # leaving a blocking constitutional rule silently inert.
            violations.extend(
                PurityChecks.check_action_pattern(tree, file_path=file_path)
            )

        elif check_type == "forbidden_decorators":
            violations.extend(
                PurityChecks.check_forbidden_decorators(
                    tree, params.get("forbidden", [])
                )
            )

        elif check_type == "no_direct_writes":
            violations.extend(
                PurityChecks.check_no_direct_writes(
                    tree,
                    taxonomy=self.fs_taxonomy,
                )
            )

        elif check_type == "forbidden_imports_and_calls":
            violations.extend(
                PurityChecks.check_forbidden_imports_and_calls(
                    tree,
                    forbidden_imports=params.get("forbidden_imports", []),
                    forbidden_calls=params.get("forbidden_calls", []),
                )
            )

        # --- AI Governance ---
        elif check_type == "prompt_model_required":
            violations.extend(
                PromptModelChecks.check_prompt_model_required(tree, params)
            )

        # --- Boundaries & Architecture ---
        elif check_type == "runtime_import_boundary":
            res = RuntimeImportBoundaryCheck.check(file_path, tree, params)
            if not res.ok:
                violations.extend(res.violations)

        elif check_type == "capability_assignment":
            violations.extend(
                self._capability_checks.check_capability_assignment(
                    tree, file_path=file_path
                )
            )

        elif check_type == "modularity":
            # Modularity checks return dicts carrying structured detail
            # (dominant_class_name, dominant_class_lines, dominant_class_ratio,
            # responsibility_count, responsibilities, etc.). Propagate the
            # full dict shape so downstream consumers can populate
            # AuditFinding.context via base.normalize_violation().
            method_name = params.get("check_method", "check_refactor_score")
            method = getattr(self._modularity_checker, method_name)
            findings = method(file_path, params)
            violations.extend(findings)

        elif check_type == "protected_namespace_access":
            violations.extend(
                ProtectedNamespaceAccessCheck.check_protected_namespace_access(
                    tree=tree,
                    file_path=file_path,
                )
            )

        elif check_type == "artifact_discovery_through_registry":
            violations.extend(
                ArtifactDiscoveryCheck.check_artifact_discovery_through_registry(
                    tree=tree,
                    file_path=file_path,
                )
            )

        elif check_type == "test_gen_acceptance_includes_pytest_gate":
            violations.extend(
                TestGenAcceptanceCheck.check(tree=tree, file_path=file_path)
            )

        elif check_type == "schema_conformance":
            schema_ref = params.get("schema_ref", "")
            contract_path = (
                self._paths.intent_root
                / "enforcement"
                / "contracts"
                / f"{schema_ref}.json"
            )
            violations.extend(
                SchemaConformanceChecks.check_schema_contract_fields(
                    tree, contract_path, str(file_path)
                )
            )

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

        elif check_type == "tempfile_default_dir":
            violations.extend(PurityChecks.check_tempfile_default_dir(tree))

        elif check_type == "future_annotations":
            violations.extend(PurityChecks.check_future_annotations(tree))

        elif check_type == "reaudit_requires_reaudit_mechanism":
            violations.extend(
                AwaitingReauditChecks.check_reaudit_requires_mechanism(tree)
            )

        elif check_type == "indeterminate_requires_human_mechanism":
            violations.extend(
                IndeterminateHumanChecks.check_indeterminate_requires_human_mechanism(
                    tree
                )
            )

        elif check_type == "test_file_naming":
            violations.extend(NamingChecks.check_test_file_naming(str(file_path)))

        elif check_type == "type_annotations":
            violations.extend(NamingChecks.check_type_annotations(tree))

        # --- API Authentication Boundary (ADR-132 D7) ---
        elif check_type == "router_exposure_enforcement":
            violations.extend(ApiAuthChecks.check_router_exposure_enforcement(tree))

        elif check_type == "route_module_must_declare_exposure":
            violations.extend(
                ApiAuthChecks.check_route_module_must_declare_exposure(tree)
            )

        elif check_type == "sensitive_route_must_be_gated":
            violations.extend(ApiAuthChecks.check_sensitive_route_must_be_gated(tree))

        # --- Logging & Channel Discipline ---
        elif check_type == "logger_not_presentation":
            violations.extend(LoggingChecks.check_logger_not_presentation(tree))

        # --- Generic & Contract Primitives ---
        elif check_type in (
            "generic_primitive",
            "required_calls",
            "decorator_args",
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

        elif check_type == "import_order":
            violations.extend(ImportChecks.check_import_order(tree, params))

        elif check_type == "module_header":
            import re

            lines = source.splitlines()
            first_line = lines[0] if lines else ""
            if not re.match(r"^# src/", first_line):
                violations.append(
                    f"Line 1: Missing or incorrect module header. "
                    f"Expected '# src/<path>', got: {first_line!r}"
                )

        else:
            # #588: unknown check_type guard. Pre-#588, an unrecognised
            # name (typo in a rule's params, drift between
            # _SUPPORTED_CHECK_TYPES and the dispatch chain, or a
            # cross-engine name like ``linter_compliance`` that belongs
            # on workflow_gate) silently fell through to the generic
            # completion return below with zero violations — invisibly
            # passing every audit. Hard-fail the dispatch instead so the
            # drift becomes visible at the verdict.
            return EngineResult(
                ok=False,
                message=f"Logic Error: Unknown check_type {check_type!r}",
                violations=[],
                engine_id=self.engine_id,
            )

        # 4. FINAL VERDICT
        return EngineResult(
            ok=(not violations),
            message=f"AST Check complete: {check_type}",
            violations=violations,
            engine_id=self.engine_id,
        )
