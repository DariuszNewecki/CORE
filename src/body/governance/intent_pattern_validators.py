# src/body/governance/intent_pattern_validators.py
"""
Pattern validators dispatched by IntentGuard.validate_generated_code.

Currently houses the ``test_file`` validator (issue #574 — write-time
import-resolution gate for generated test code). Rule statements are
looked up from ``IntentRepository`` by id; the executor lives in code,
the rule lives in ``.intent/``.
"""

from __future__ import annotations

import ast
import importlib.util

from mind.governance.violation_report import ViolationReport
from shared.logger import getLogger


logger = getLogger(__name__)

_GENERATED_RESOLVE_RULE_ID = "code.imports.generated_must_resolve"
_GENERATED_NO_RELATIVE_RULE_ID = "code.imports.generated_no_relative"


# ID: 5d89fc56-2fb5-45da-98f0-f813e8e79343
class PatternValidators:
    """Pattern validators dispatched by ``PatternValidators.validate``.

    Each registered ``pattern_id`` maps to a classmethod that walks the
    generated code and returns ``list[ViolationReport]``. Unknown
    ``pattern_id`` values fall through to an empty-list result (deliberate
    "no validator applies" — see ``validate``'s docstring).
    """

    _RULE_STATEMENT_CACHE: dict[str, str] | None = None

    @classmethod
    # ID: 2781e0e8-0fff-4764-8c11-b6cfbc508a65
    def validate_test_file_pattern(
        cls, code: str, target_path: str
    ) -> list[ViolationReport]:
        """Validate generated test code for import resolution + absolute-import discipline.

        Closes #574 — IntentGuard.validate_generated_code previously accepted
        hallucinated imports for ``pattern_id="test_file"`` (no validator was
        registered). The two rules enforced here are declared in
        ``.intent/rules/code/imports.json`` and looked up by id from
        ``IntentRepository``; the validator holds the executor (AST walker +
        ``importlib.util.find_spec``), the rule statement lives in ``.intent/``.

        Rules enforced:
        - ``code.imports.generated_must_resolve`` — every absolute ``import`` /
          ``from M import …`` must resolve to a module on the Python path.
          ``__future__`` imports are skipped (always valid).
        - ``code.imports.generated_no_relative`` — relative imports
          (``from .foo import x``, ``from ..pkg import y``) are forbidden in
          generated code. Reported, and the resolve check is skipped for the
          same node (relative imports do not have an absolute module name
          ``find_spec`` could resolve).

        Out of scope (intentional, MVP for #574):
        - Whether a name imported from a real module actually exists in that
          module (e.g. ``from os import not_a_real_function``). Would require
          actually importing the module and inspecting attributes.
        - Dynamic imports (``importlib.import_module(...)``). Not visible to AST.
        - Semantic correctness of test assertions. Separate issue.
        """
        violations: list[ViolationReport] = []

        try:
            tree = ast.parse(code)
        except SyntaxError:
            # validate_generated_code step 2 already catches and reports
            # SyntaxError; re-emitting from here would duplicate the violation.
            return []

        statements = cls._load_generated_import_rule_statements()

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == "__future__":
                    continue
                if node.level > 0:
                    violations.append(
                        ViolationReport(
                            rule_name=_GENERATED_NO_RELATIVE_RULE_ID,
                            path=target_path,
                            message=statements.get(
                                _GENERATED_NO_RELATIVE_RULE_ID,
                                "Generated code MUST use absolute imports; relative imports are forbidden.",
                            ),
                            severity="error",
                            suggested_fix="Replace the relative import with an absolute module path.",
                            source_policy="rules.code.imports",
                        )
                    )
                    continue
                if node.module and not cls._module_resolves(node.module):
                    violations.append(
                        ViolationReport(
                            rule_name=_GENERATED_RESOLVE_RULE_ID,
                            path=target_path,
                            message=statements.get(
                                _GENERATED_RESOLVE_RULE_ID,
                                "Generated code MUST have every import resolve to an existing module.",
                            )
                            + f" Unresolvable module: {node.module!r}.",
                            severity="error",
                            suggested_fix=(
                                f"Replace {node.module!r} with a module that exists on the Python path, "
                                "or remove the import if unused."
                            ),
                            source_policy="rules.code.imports",
                        )
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name
                    if not cls._module_resolves(module_name):
                        violations.append(
                            ViolationReport(
                                rule_name=_GENERATED_RESOLVE_RULE_ID,
                                path=target_path,
                                message=statements.get(
                                    _GENERATED_RESOLVE_RULE_ID,
                                    "Generated code MUST have every import resolve to an existing module.",
                                )
                                + f" Unresolvable module: {module_name!r}.",
                                severity="error",
                                suggested_fix=(
                                    f"Replace {module_name!r} with a module that exists on the Python path, "
                                    "or remove the import if unused."
                                ),
                                source_policy="rules.code.imports",
                            )
                        )

        return violations

    @staticmethod
    def _module_resolves(module_name: str) -> bool:
        """Return True iff ``importlib.util.find_spec(module_name)`` finds a spec.

        ``find_spec`` raises on malformed names or when a parent package fails
        to import (its own broken import). Treated identically here: any
        exception means "does not resolve cleanly", which is the property the
        generated-must-resolve rule cares about.
        """
        try:
            return importlib.util.find_spec(module_name) is not None
        except (ModuleNotFoundError, ImportError, ValueError):
            return False

    @classmethod
    def _load_generated_import_rule_statements(cls) -> dict[str, str]:
        """Look up the two generated-import rule statements from IntentRepository.

        Lazy-loaded and cached on the class. On any lookup failure (missing
        rule, repository init failure) returns an empty dict; callers fall
        back to placeholder text so the validator still surfaces violations
        even when ``.intent/`` is degraded — fail-loud on the gate, fail-soft
        on the messaging.
        """
        if cls._RULE_STATEMENT_CACHE is not None:
            return cls._RULE_STATEMENT_CACHE

        try:
            from shared.infrastructure.intent.intent_repository import (
                get_intent_repository,
            )

            repo = get_intent_repository()
            repo.initialize()
            wanted = {_GENERATED_RESOLVE_RULE_ID, _GENERATED_NO_RELATIVE_RULE_ID}
            cache: dict[str, str] = {}
            for rule in repo.find_rules():
                rid = rule.get("id") if isinstance(rule, dict) else None
                if rid in wanted:
                    statement = (
                        rule.get("statement", "") if isinstance(rule, dict) else ""
                    )
                    if statement:
                        cache[rid] = statement
            cls._RULE_STATEMENT_CACHE = cache
        except Exception as exc:
            logger.warning(
                "PatternValidators: failed to load generated-import rule statements "
                "from IntentRepository — falling back to inline messages. Reason: %s",
                exc,
            )
            cls._RULE_STATEMENT_CACHE = {}

        return cls._RULE_STATEMENT_CACHE

    @classmethod
    # ID: 88f6ecff-74fe-469c-aa00-7fea3a8e1831
    def validate(
        cls,
        code: str,
        pattern_id: str,
        component_type: str,
        target_path: str = "",
    ) -> list[ViolationReport]:
        """Dispatch to the appropriate per-pattern validator by ``pattern_id``.

        Issue #210: prior IntentGuard call invoked a method that did not
        exist, raising AttributeError that was silently swallowed by a
        broad except in build.tests. This classmethod is the canonical
        entry point.

        Returns an empty list when ``pattern_id`` does not correspond to
        any per-pattern validator. That is a deliberate "no validator
        applies" signal — not a failure — and is logged at INFO so the gap
        remains observable. Real validator failures must surface as
        exceptions or violations from the per-pattern validator itself,
        never as a silent empty list.

        ``component_type`` is accepted for API stability with the existing
        IntentGuard call shape but is currently unused — reserved for
        future per-component-type dispatch.
        """
        dispatch = {
            "test_file": cls.validate_test_file_pattern,
        }
        validator = dispatch.get(pattern_id)
        if validator is None:
            logger.info(
                "PatternValidators: no validator for pattern_id=%r "
                "(component_type=%r) — returning empty violations",
                pattern_id,
                component_type,
            )
            return []
        return validator(code, target_path)
