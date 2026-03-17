# src/mind/logic/engines/ast_gate/checks/intent_access_check.py

from __future__ import annotations

import ast
from pathlib import Path
from typing import ClassVar


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

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                tainted_names |= cls._collect_tainted_assignments(node)

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                findings.extend(cls._check_call(node, tainted_names))

        return findings

    @classmethod
    def _collect_tainted_assignments(cls, node: ast.Assign) -> set[str]:
        """Track variables that are assigned from .intent-related expressions."""
        if not cls._expr_is_intent_related(node.value):
            return set()

        tainted: set[str] = set()
        for target in node.targets:
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
    def _check_call(cls, node: ast.Call, tainted_names: set[str]) -> list[str]:
        """Inspect a call node for unauthorized .intent usage."""
        findings: list[str] = []
        call_name = cls._full_attr_name(node.func) or ""

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
