# src/mind/logic/engines/ast_gate/checks/protected_namespace_access_check.py

"""
ProtectedNamespaceAccessCheck — flags unauthorized direct access to
protected filesystem namespaces outside their sanctioned gateway.

Renamed from `IntentAccessCheck` (issue #490, deferred from ADR-077).
The old name described the original scope (`.intent/` only). The
generalised name announces ADR-077's intent: any namespace that should
be reached only through a gateway is the same shape of constraint.

This commit performs the rename only. The taint-tracking semantics —
markers, gateway path, traversal/read/parse call sets — remain
hardcoded to `.intent/` to preserve byte-equivalent behaviour for the
existing `architecture.namespace.no_direct_protected_access` rule.
Promoting these to rule-supplied parameters (per ADR-077's
generalisation goal) is separate follow-up work and is intentionally
out of scope for this commit; #490 explicitly limited itself to the
naming cleanup so the symbol-index ripple is taken in one bounded
change.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import ClassVar

from ..base import ASTHelpers


# ID: fb3ec00a-bc27-40ce-b8d9-47b10d25292b
class ProtectedNamespaceAccessCheck:
    """Detect unauthorized direct access to a protected namespace.

    Currently parameterised at the class-constant level for `.intent/`.
    Future work (separate ADR/issue) will accept `protected_markers`,
    `gateway_segment`, and `forbidden_classes` as rule-supplied
    parameters so additional protected namespaces can declare rules
    without modifying engine code.
    """

    _GATEWAY_SEGMENT: ClassVar[str] = "src/shared/infrastructure/intent/"

    _TRAVERSAL_CALLS: ClassVar[frozenset[str]] = frozenset(
        {
            "glob",
            "rglob",
            "iterdir",
            "walk",
        }
    )

    _READ_CALLS: ClassVar[frozenset[str]] = frozenset(
        {
            "read_text",
            "read_bytes",
            "open",
        }
    )

    _PARSE_CALLS: ClassVar[frozenset[str]] = frozenset(
        {
            "yaml.safe_load",
            "yaml.safe_load_all",
            "yaml.load",
            "json.load",
            "json.loads",
        }
    )

    _PROTECTED_MARKERS: ClassVar[frozenset[str]] = frozenset(
        {
            ".intent",
            "/.intent/",
            ".intent/",
            "intent_root",
        }
    )

    @classmethod
    # ID: 411e3fa1-2620-42c5-bdba-6602a207b8f7
    def check_protected_namespace_access(
        cls,
        tree: ast.AST,
        file_path: Path,
    ) -> list[str]:
        """
        Flag unauthorized protected-namespace access outside the sanctioned gateway.

        Detection strategy:
        1. Ignore files inside the gateway segment
        2. Track variables assigned from namespace-tainted expressions
        3. Report traversal/read/parse behavior on those variables
        4. Report direct namespace traversal/read expressions even without aliasing
        """
        normalized_path = str(file_path).replace("\\", "/")
        if cls._GATEWAY_SEGMENT in normalized_path:
            return []

        findings: list[str] = []
        tainted_names: set[str] = set()
        alias_map = ASTHelpers.build_import_alias_map(tree)

        # Pass 1 — collect tainted variables across plain, annotated, and
        # augmented assignments. The growing tainted_names set is threaded
        # through so multi-hop derivations propagate (issue #119, gap 1).
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                tainted_names |= cls._collect_tainted_assignments(node, tainted_names)

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                findings.extend(cls._check_call(node, tainted_names, alias_map))

        return findings

    @classmethod
    def _collect_tainted_assignments(
        cls,
        node: ast.Assign | ast.AnnAssign | ast.AugAssign,
        tainted_names: set[str],
    ) -> set[str]:
        """Track variables that are assigned from namespace-tainted expressions.

        Handles plain (``x = ...``), annotated (``x: T = ...``), and augmented
        (``x /= ...``) assignments. ``tainted_names`` is threaded in from the
        caller so multi-hop chains propagate — a variable derived from a
        previously-tainted name is itself tainted.

        Single-pass accumulation: ast.walk visits sibling statements in
        source order, which is sufficient for the common case where the
        derivation appears on consecutive lines. Multi-hop chains where the
        intermediate assignment appears AFTER the usage in source order are
        not detected — known limit of intraprocedural single-pass analysis
        (issue #119, gap 4).

        For augmented assignments, the target is also kept tainted when the
        target name was already tainted before this statement.
        """
        if isinstance(node, ast.AnnAssign) and node.value is None:
            return set()

        if isinstance(node, ast.Assign):
            target_nodes: list[ast.AST] = list(node.targets)
        else:
            target_nodes = [node.target]

        value_is_protected = cls._expr_is_protected(node.value, tainted_names)

        target_already_tainted = False
        if isinstance(node, ast.AugAssign):
            existing: set[str] = set()
            for tgt in target_nodes:
                existing |= cls._extract_target_names(tgt)
            target_already_tainted = bool(existing & tainted_names)

        if not value_is_protected and not target_already_tainted:
            return set()

        tainted: set[str] = set()
        for target in target_nodes:
            tainted |= cls._extract_target_names(target)
        return tainted

    @classmethod
    def _extract_target_names(cls, node: ast.AST) -> set[str]:
        """Extract names assigned by an assignment target."""
        names: set[str] = set()

        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, (ast.Tuple, ast.List)):
            for elt in node.elts:
                names |= cls._extract_target_names(elt)

        return names

    @classmethod
    def _check_call(
        cls,
        node: ast.Call,
        tainted_names: set[str],
        alias_map: dict[str, str] | None = None,
    ) -> list[str]:
        """Inspect a call node for unauthorized protected-namespace usage."""
        findings: list[str] = []
        if alias_map is None:
            alias_map = {}
        call_name = ASTHelpers.resolve_qualified_name(node.func, alias_map) or ""

        if call_name in cls._PARSE_CALLS and any(
            cls._expr_is_protected(arg, tainted_names) for arg in node.args
        ):
            findings.append(
                f"Line {getattr(node, 'lineno', '?')}: Direct parsing of protected-namespace content via '{call_name}()' outside the sanctioned gateway."
            )

        if isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            receiver = node.func.value

            if attr in cls._TRAVERSAL_CALLS and cls._expr_is_protected(
                receiver, tainted_names
            ):
                findings.append(
                    f"Line {getattr(node, 'lineno', '?')}: Direct protected-namespace traversal via '{attr}()' outside the sanctioned gateway."
                )

            if attr in cls._READ_CALLS and cls._expr_is_protected(
                receiver, tainted_names
            ):
                findings.append(
                    f"Line {getattr(node, 'lineno', '?')}: Direct protected-namespace read via '{attr}()' outside the sanctioned gateway."
                )

        if call_name == "open" and node.args:
            if cls._expr_is_protected(node.args[0], tainted_names):
                findings.append(
                    f"Line {getattr(node, 'lineno', '?')}: Direct protected-namespace open() outside the sanctioned gateway."
                )

        return findings

    @classmethod
    def _expr_is_protected(
        cls,
        node: ast.AST | None,
        tainted_names: set[str] | None = None,
    ) -> bool:
        """Return True when an expression is clearly tied to protected-namespace access."""
        if node is None:
            return False

        if tainted_names is None:
            tainted_names = set()

        if isinstance(node, ast.Name) and node.id in tainted_names:
            return True

        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return cls._string_is_protected(node.value)

        if isinstance(node, ast.JoinedStr):
            for value in node.values:
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    if cls._string_is_protected(value.value):
                        return True
            return False

        if isinstance(node, ast.Attribute):
            full_name = cls._full_attr_name(node) or ""
            if full_name.endswith("intent_root") or ".intent_root" in full_name:
                return True
            return cls._expr_is_protected(node.value, tainted_names)

        if isinstance(node, ast.BinOp):
            return cls._expr_is_protected(
                node.left, tainted_names
            ) or cls._expr_is_protected(node.right, tainted_names)

        if isinstance(node, ast.Call):
            func_name = cls._full_attr_name(node.func) or ""
            if func_name == "Path" and any(
                cls._expr_is_protected(arg, tainted_names) for arg in node.args
            ):
                return True

            if isinstance(node.func, ast.Attribute) and cls._expr_is_protected(
                node.func.value, tainted_names
            ):
                return True

            return any(cls._expr_is_protected(arg, tainted_names) for arg in node.args)

        if isinstance(node, ast.Subscript):
            return cls._expr_is_protected(node.value, tainted_names)

        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            return any(cls._expr_is_protected(elt, tainted_names) for elt in node.elts)

        return False

    @classmethod
    def _string_is_protected(cls, value: str) -> bool:
        """Check whether a string literal references a protected namespace."""
        normalized = value.replace("\\", "/")
        return any(marker in normalized for marker in cls._PROTECTED_MARKERS)

    @classmethod
    def _full_attr_name(cls, node: ast.AST) -> str | None:
        """Return dotted name for Name/Attribute chains."""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            root = cls._full_attr_name(node.value)
            return f"{root}.{node.attr}" if root else node.attr
        return None
