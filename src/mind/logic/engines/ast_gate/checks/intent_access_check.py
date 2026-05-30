# src/mind/logic/engines/ast_gate/checks/intent_access_check.py

from __future__ import annotations

import ast
from pathlib import Path
from typing import ClassVar

from ..base import ASTHelpers


# ID: 9f6c6a4d-2d39-4a54-a6ab-1e3d4136d8d1
class IntentAccessCheck:
    """Detect unauthorized direct .intent access."""

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

    _INTENT_MARKERS: ClassVar[frozenset[str]] = frozenset(
        {
            ".intent",
            "/.intent/",
            ".intent/",
            "intent_root",
        }
    )

    @classmethod
    # ID: 411e3fa1-2620-42c5-bdba-6602a207b8f7
    def check_direct_intent_access(
        cls,
        tree: ast.AST,
        file_path: Path,
    ) -> list[str]:
        """
        Flag unauthorized .intent access outside the sanctioned gateway.

        Detection strategy:
        1. Ignore files inside src/shared/infrastructure/intent/**
        2. Track variables assigned from .intent-ish expressions
        3. Report traversal/read/parse behavior on those variables
        4. Report direct .intent traversal/read expressions even without aliasing
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
        """Track variables that are assigned from .intent-related expressions.

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
        target name was already tainted before this statement (e.g.
        ``path /= "subdir"`` after ``path = self.intent_root`` — value alone
        is not intent-related, but the assignment must not silently
        un-taint the variable).
        """
        # Bare type annotation with no RHS — nothing to propagate.
        if isinstance(node, ast.AnnAssign) and node.value is None:
            return set()

        if isinstance(node, ast.Assign):
            target_nodes: list[ast.AST] = list(node.targets)
        else:
            target_nodes = [node.target]

        value_is_intent = cls._expr_is_intent_related(node.value, tainted_names)

        # Augmented assignment never un-taints: if any target name was
        # already in the tainted set, keep it there even when value is clean.
        target_already_tainted = False
        if isinstance(node, ast.AugAssign):
            existing: set[str] = set()
            for tgt in target_nodes:
                existing |= cls._extract_target_names(tgt)
            target_already_tainted = bool(existing & tainted_names)

        if not value_is_intent and not target_already_tainted:
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
        """Inspect a call node for unauthorized .intent usage.

        ``alias_map`` carries the {local_name: qualified_name} translation
        from imports, so PARSE_CALLS lookups match both
        ``yaml.safe_load(...)`` AND ``from yaml import safe_load;
        safe_load(...)``. Defaults to empty for callers that have not yet
        threaded the resolver (behavioural parity with pre-#488 callers).
        """
        findings: list[str] = []
        if alias_map is None:
            alias_map = {}
        call_name = ASTHelpers.resolve_qualified_name(node.func, alias_map) or ""

        if call_name in cls._PARSE_CALLS and any(
            cls._expr_is_intent_related(arg, tainted_names) for arg in node.args
        ):
            findings.append(
                f"Line {getattr(node, 'lineno', '?')}: Direct parsing of .intent content via '{call_name}()' outside shared intent infrastructure."
            )

        if isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            receiver = node.func.value

            if attr in cls._TRAVERSAL_CALLS and cls._expr_is_intent_related(
                receiver, tainted_names
            ):
                findings.append(
                    f"Line {getattr(node, 'lineno', '?')}: Direct .intent traversal via '{attr}()' outside shared intent infrastructure."
                )

            if attr in cls._READ_CALLS and cls._expr_is_intent_related(
                receiver, tainted_names
            ):
                findings.append(
                    f"Line {getattr(node, 'lineno', '?')}: Direct .intent read via '{attr}()' outside shared intent infrastructure."
                )

        if call_name == "open" and node.args:
            if cls._expr_is_intent_related(node.args[0], tainted_names):
                findings.append(
                    f"Line {getattr(node, 'lineno', '?')}: Direct .intent open() outside shared intent infrastructure."
                )

        return findings

    @classmethod
    def _expr_is_intent_related(
        cls,
        node: ast.AST | None,
        tainted_names: set[str] | None = None,
    ) -> bool:
        """Return True when an expression is clearly tied to .intent access."""
        if node is None:
            return False

        if tainted_names is None:
            tainted_names = set()

        if isinstance(node, ast.Name) and node.id in tainted_names:
            return True

        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return cls._string_is_intent_related(node.value)

        if isinstance(node, ast.JoinedStr):
            for value in node.values:
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    if cls._string_is_intent_related(value.value):
                        return True
            return False

        if isinstance(node, ast.Attribute):
            full_name = cls._full_attr_name(node) or ""
            if full_name.endswith("intent_root") or ".intent_root" in full_name:
                return True
            return cls._expr_is_intent_related(node.value, tainted_names)

        if isinstance(node, ast.BinOp):
            return cls._expr_is_intent_related(
                node.left, tainted_names
            ) or cls._expr_is_intent_related(node.right, tainted_names)

        if isinstance(node, ast.Call):
            func_name = cls._full_attr_name(node.func) or ""
            if func_name == "Path" and any(
                cls._expr_is_intent_related(arg, tainted_names) for arg in node.args
            ):
                return True

            if isinstance(node.func, ast.Attribute) and cls._expr_is_intent_related(
                node.func.value, tainted_names
            ):
                return True

            return any(
                cls._expr_is_intent_related(arg, tainted_names) for arg in node.args
            )

        if isinstance(node, ast.Subscript):
            return cls._expr_is_intent_related(node.value, tainted_names)

        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            return any(
                cls._expr_is_intent_related(elt, tainted_names) for elt in node.elts
            )

        return False

    @classmethod
    def _string_is_intent_related(cls, value: str) -> bool:
        """Check whether a string literal references .intent."""
        normalized = value.replace("\\", "/")
        return any(marker in normalized for marker in cls._INTENT_MARKERS)

    @classmethod
    def _full_attr_name(cls, node: ast.AST) -> str | None:
        """Return dotted name for Name/Attribute chains."""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            root = cls._full_attr_name(node.value)
            return f"{root}.{node.attr}" if root else node.attr
        return None
