# src/mind/logic/engines/ast_gate/checks/purity_checks.py
"""
Purity Checks - Deterministic AST-based enforcement.

Focused on rules from .intent/policies/code/purity.json and adjacent purity constraints.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import ClassVar

from mind.logic.engines.ast_gate.base import ASTHelpers


# ID: 6b2a85b5-2b76-4db7-bfb4-4f3a8b7b5f11
class PurityChecks:
    """
    Stateless check collection for the AST gate engine.
    Each check returns a list[str] of human-readable violations.
    """

    # ID: 9b3f3c34-2bba-4cf1-9d8b-51d548a61b7e
    _ID_ANCHOR_PREFIXES: ClassVar[tuple[str, ...]] = ("# ID:",)

    @staticmethod
    # ID: e4d3c2b1-a0f9-8e7d-6c5b-4a3f2e1d0c9b
    def _extract_domain_from_path(file_path: Path | str) -> str:
        """
        Extract domain from file path following CORE's domain convention.

        Examples:
            src/mind/governance/foo.py -> mind.governance
            /opt/dev/CORE/src/body/cli/logic/bar.py -> body.cli.logic
            src/features/example/baz.py -> features.example

        Returns empty string if path doesn't match convention.
        """
        # Convert to string and normalize path separators
        path_str = str(file_path).replace("\\", "/")

        # Find the 'src/' marker and extract everything after it
        if "/src/" in path_str:
            # Split on /src/ and take the part after it
            path_str = path_str.split("/src/", 1)[1]
        elif path_str.startswith("src/"):
            # Already relative, remove src/ prefix
            path_str = path_str[4:]
        else:
            # No src/ found, use as-is
            pass

        # Split path and take domain parts (before filename)
        parts = path_str.split("/")

        # Filter out filename (last part with .py) and empty parts
        domain_parts = [p for p in parts[:-1] if p]

        # Join with dots to form domain
        return ".".join(domain_parts) if domain_parts else ""

    @staticmethod
    # ID: f3e2d1c0-b9a8-7f6e-5d4c-3b2a1f0e9d8c
    def _domain_matches_allowed(file_domain: str, allowed_domains: list[str]) -> bool:
        """
        Check if file domain matches any allowed domain.

        Supports prefix matching:
            - file_domain="mind.governance.checks" matches allowed="mind.governance"
            - file_domain="body.cli.logic" matches allowed="body.cli.logic"

        Args:
            file_domain: Domain extracted from file path (e.g., "mind.governance.checks")
            allowed_domains: List of allowed domain prefixes

        Returns:
            True if file_domain starts with any allowed domain
        """
        if not file_domain or not allowed_domains:
            return False

        for allowed in allowed_domains:
            # Exact match or prefix match
            if file_domain == allowed or file_domain.startswith(f"{allowed}."):
                return True

        return False

    @staticmethod
    # ID: 7b2f0a5a-cf7d-4af4-9b3c-7bbd7b4d36d4
    def check_stable_id_anchor(source: str) -> list[str]:
        """
        Ensures that the file contains at least one stable ID anchor.
        This is intentionally simple: many other tools rely on '# ID:' anchors.
        """
        lines = source.splitlines()
        for line in lines[:200]:  # cheap bound; IDs should be near top or near symbols
            stripped = line.strip()
            if any(stripped.startswith(p) for p in PurityChecks._ID_ANCHOR_PREFIXES):
                return []
        return ["Missing stable ID anchor: expected at least one '# ID: <...>' line."]

    @staticmethod
    # ID: 1cc2a7f3-5e21-4c10-9f93-5d2b7bdb3a65
    def check_forbidden_decorators(tree: ast.AST, forbidden: list[str]) -> list[str]:
        violations: list[str] = []
        forbidden_set = {
            d.strip() for d in forbidden if isinstance(d, str) and d.strip()
        }
        if not forbidden_set:
            return violations

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            for dec in node.decorator_list:
                dec_name = ASTHelpers.full_attr_name(dec)
                if dec_name in forbidden_set:
                    violations.append(
                        f"Forbidden decorator '{dec_name}' on function '{node.name}' (line {ASTHelpers.lineno(dec)})."
                    )

        return violations

    @staticmethod
    # ID: 8d7c6b5a-4e3f-2d1c-0b9a-8f7e6d5c4b3a
    def check_forbidden_primitives(
        tree: ast.AST,
        forbidden: list[str],
        file_path: Path | None = None,
        allowed_domains: list[str] | None = None,
    ) -> list[str]:
        """
        Check for forbidden execution primitives with domain-aware trust zones.

        Constitutional Rule: agent.execution.no_unverified_code

        Args:
            tree: AST tree to check
            forbidden: List of forbidden primitive names (e.g., ["eval", "exec", "compile", "__import__"])
            file_path: Optional file path to determine domain
            allowed_domains: Optional list of domain prefixes where primitives are allowed

        Returns:
            List of violation messages

        Examples:
            # File in allowed domain (mind.governance) - primitives allowed
            check_forbidden_primitives(tree, ["eval"], Path("src/mind/governance/checks/test.py"),
                                       ["mind.governance", "body.cli.logic"])
            # Returns: []

            # File in forbidden domain (features) - primitives forbidden
            check_forbidden_primitives(tree, ["eval"], Path("src/features/example/service.py"),
                                       ["mind.governance", "body.cli.logic"])
            # Returns: ["Dangerous primitive 'eval' is FORBIDDEN in this domain..."]
        """
        violations: list[str] = []
        forbidden_set = {
            p.strip() for p in forbidden if isinstance(p, str) and p.strip()
        }
        if not forbidden_set:
            return violations

        # Determine if file is in allowed trust zone
        is_allowed_domain = False
        file_domain = ""

        if file_path and allowed_domains:
            file_domain = PurityChecks._extract_domain_from_path(file_path)
            is_allowed_domain = PurityChecks._domain_matches_allowed(
                file_domain, allowed_domains
            )

        for node in ast.walk(tree):
            primitive_name = None

            # Check for Name nodes (e.g., eval, exec)
            if isinstance(node, ast.Name) and node.id in forbidden_set:
                primitive_name = node.id
            # Check for Attribute nodes (e.g., builtins.eval)
            elif isinstance(node, ast.Attribute):
                name = ASTHelpers.full_attr_name(node)
                if name and name in forbidden_set:
                    primitive_name = name

            if primitive_name:
                if is_allowed_domain:
                    # In allowed domain - primitive is permitted
                    continue
                else:
                    # Not in allowed domain - violation
                    if allowed_domains:
                        allowed_str = ", ".join(allowed_domains)
                        violations.append(
                            f"Dangerous primitive '{primitive_name}' is FORBIDDEN in this domain. "
                            f"Allowed domains: {allowed_str} (current domain: {file_domain or 'unknown'}) "
                            f"(line {ASTHelpers.lineno(node)})."
                        )
                    else:
                        violations.append(
                            f"Forbidden primitive '{primitive_name}' used (line {ASTHelpers.lineno(node)})."
                        )

        return violations

    @staticmethod
    # ID: 3e2f4d95-02db-4f55-9fdb-9e55f9a9d918
    def check_no_print_statements(tree: ast.AST) -> list[str]:
        violations: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                call_name = ASTHelpers.full_attr_name(node.func)
                if call_name == "print":
                    violations.append(
                        f"Forbidden print() call on line {ASTHelpers.lineno(node)}. "
                        "Use logger.info() or logger.debug() instead."
                    )
        return violations

    @staticmethod
    # ID: a4b3c2d1-e0f9-8e7d-6c5b-4a3f2e1d0c9b
    def check_required_decorator(
        tree: ast.AST,
        decorator: str,
        only_public: bool = True,
        ignore_tests: bool = True,
    ) -> list[str]:
        """
        Check that state-modifying functions have required decorator.

        Heuristic for state-modifying: function contains assignment, attribute setting, or method calls.
        """
        violations: list[str] = []

        def _has_decorator(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
            for dec in node.decorator_list:
                dec_name = ASTHelpers.full_attr_name(dec)
                if dec_name == decorator:
                    return True
            return False

        def _looks_state_modifying(
            node: ast.FunctionDef | ast.AsyncFunctionDef,
        ) -> bool:
            """Heuristic: does function look like it modifies state?"""
            writeish = {"Assign", "AugAssign", "AnnAssign", "Delete"}
            for child in ast.walk(node):
                leaf = type(child).__name__.split(".")[-1]
                if leaf in writeish:
                    return True
            return False

        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            if ignore_tests and fn.name.startswith("test_"):
                continue
            if only_public and fn.name.startswith("_"):
                continue

            if _looks_state_modifying(fn) and not _has_decorator(fn):
                violations.append(
                    f"Function '{fn.name}' appears state-modifying but lacks required @{decorator} "
                    f"(line {ASTHelpers.lineno(fn)})."
                )

        return violations

    @staticmethod
    # ID: 2dd7a4b8-fc4e-468e-9a1a-315acb2b3d6f
    def check_decorator_args(
        tree: ast.AST, decorator: str, required_args: list[str]
    ) -> list[str]:
        """
        Enforces that @<decorator>(...) includes all required keyword args.

        Example policy:
            check_type: decorator_args
            decorator: atomic_action
            required_args: ["action_id", "impact", "policies"]
        """
        violations: list[str] = []
        required = [
            a.strip() for a in required_args if isinstance(a, str) and a.strip()
        ]
        required_set = set(required)
        if not required_set:
            return violations

        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            # Find the decorator occurrence(s)
            for dec in fn.decorator_list:
                # @atomic_action  (no call) -> violation because args cannot exist
                if isinstance(dec, ast.Name) and dec.id == decorator:
                    violations.append(
                        f"@{decorator} on '{fn.name}' must be called with arguments "
                        f"{sorted(required_set)} (line {ASTHelpers.lineno(dec)})."
                    )
                    continue

                # @x.atomic_action  (no call)
                if (
                    isinstance(dec, ast.Attribute)
                    and ASTHelpers.full_attr_name(dec) == decorator
                ):
                    violations.append(
                        f"@{decorator} on '{fn.name}' must be called with arguments "
                        f"{sorted(required_set)} (line {ASTHelpers.lineno(dec)})."
                    )
                    continue

                # @atomic_action(...)
                if isinstance(dec, ast.Call):
                    call_name = ASTHelpers.full_attr_name(dec.func)
                    if (
                        call_name != decorator
                        and (call_name or "").split(".")[-1] != decorator
                    ):
                        continue

                    # Collect keyword arg names actually present
                    present_kw = {kw.arg for kw in dec.keywords if kw.arg}
                    missing = sorted(list(required_set - present_kw))

                    if missing:
                        violations.append(
                            f"@{decorator} on '{fn.name}' missing required args {missing} "
                            f"(line {ASTHelpers.lineno(dec)})."
                        )

        return violations
