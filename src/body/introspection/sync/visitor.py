# src/body/introspection/sync/visitor.py

"""Refactored logic for src/features/introspection/sync/visitor.py.

ADR-151 D5: this visitor is the marker-attribution point for the dead-shim
reaper — symbols that self-declare as deprecated (and are neither properties
nor runtime-dispatch registrations) are recorded with state='deprecated',
activating the dormant vocabulary core.symbols already carries.
"""

from __future__ import annotations

import ast
import json
import re
import uuid
from typing import Any

from shared.ast_utility import FunctionCallVisitor, calculate_structural_hash


# ADR-151 D1 marker set (iii): closed SELF-DECLARATION vocabulary, measured
# against the live tree (see the ADR's verification note). Prose that merely
# mentions legacy does NOT qualify — that broad match stays a file-level
# pre-selector (modernization.legacy_signal). Bare "legacy" openers are
# deliberately absent: "Legacy Scanner Logic" (a module that *processes*
# legacy) is the measured counter-example. Applied to the docstring's FIRST
# LINE only — a symbol self-declares in its summary line; deeper prose is
# documentation (measured counter-example: AuditFinding's Notes documenting
# a member as "a backwards-compatible alias" — the class itself is live).
# "DO NOT USE" (case-sensitive, the shouty tombstone form) covers the
# "LEGACY / DEPRECATED — DO NOT USE" module shape (sync_manifest).
_SELF_DECLARATION_RE = re.compile(
    r"(?i:^\s*deprecated\b)"
    r"|(?i:\b(?:deprecated\s+(?:alias|shim)|compatibility\s+shim"
    r"|backwards?[-\s]compatible\s+alias|legacy[-\s]compatible\s+wrapper"
    r"|retained\s+for\s+one\s+release)\b)"
    r"|\bDO NOT USE\b"
)

# Set (i): the sphinx directive is structured markup — matched anywhere in
# the docstring, not just the first line.
_DEPRECATED_DIRECTIVE_RE = re.compile(r"\.\.\s+deprecated::")


def _first_line(doc: str) -> str:
    return doc.strip().splitlines()[0] if doc.strip() else ""


# ADR-151 D1: attribute reads are not call edges — the static graph cannot
# vouch orphanhood for properties, so they never enter the automatic rule.
_PROPERTY_DECORATORS = frozenset(
    {"property", "cached_property", "setter", "getter", "deleter"}
)

# ADR-151 D2: runtime-dispatch registrations have graph-invisible callers
# (humans, dispatchers) — deprecated CLI aliases etc. are deliberate UX
# shims whose retirement is a surface decision, not an automatic reap.
_DISPATCH_DECORATORS = frozenset(
    {"command", "callback", "register_action", "get", "post", "put", "delete", "patch"}
)


def _decorator_names(
    node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
) -> set[str]:
    """Trailing name of each decorator (``router.get`` → ``get``)."""
    names: set[str] = set()
    for dec in node.decorator_list:
        target = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(target, ast.Attribute):
            names.add(target.attr)
        elif isinstance(target, ast.Name):
            names.add(target.id)
    return names


def _self_declares_deprecated(
    node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    """ADR-151 D1 sets (i)/(ii)/(iii): directive, DeprecationWarning, or
    first-line docstring self-declaration."""
    doc = ast.get_docstring(node) or ""
    if _DEPRECATED_DIRECTIVE_RE.search(doc):
        return True
    if _SELF_DECLARATION_RE.search(_first_line(doc)):
        return True
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and sub.id == "DeprecationWarning":
            return True
        if isinstance(sub, ast.Attribute) and sub.attr == "DeprecationWarning":
            return True
    return False


# ID: d766fc43-dea6-4156-8fe9-f9577416ad31
class SymbolVisitor(ast.NodeVisitor):
    """
    An AST visitor that discovers top-level public symbols, their immediate methods,
    and the symbols they call.
    """

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        self.symbols: list[dict[str, Any]] = []
        self.class_stack: list[str] = []
        self._module_deprecated = False

    # ID: 45a23a11-9ed6-4ff3-aa30-d6783478b060
    def visit_Module(self, node: ast.Module) -> None:
        # ADR-151 D1 module→symbol attribution: a module docstring carrying a
        # self-declaration in its FIRST LINE (the embedding_provider shape —
        # "Compatibility shim for legacy imports"; the sync_manifest shape —
        # "LEGACY / DEPRECATED — DO NOT USE") deprecates every public symbol
        # defined in it. A module docstring merely mentioning legacy does not.
        module_doc = ast.get_docstring(node) or ""
        self._module_deprecated = bool(
            _SELF_DECLARATION_RE.search(_first_line(module_doc))
        )
        self.generic_visit(node)

    # ID: e7f6fab3-cf81-46ff-b2d1-21d7b6f311c6
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if not self.class_stack:
            self._process_symbol(node)
            self.class_stack.append(node.name)
            self.generic_visit(node)
            self.class_stack.pop()

    # ID: 056a919f-fe43-4bab-9398-48c93c971545
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if len(self.class_stack) <= 1:
            self._process_symbol(node)

    # ID: aae1a414-338b-4a62-bb93-5a5a6b22a1fa
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        if len(self.class_stack) <= 1:
            self._process_symbol(node)

    def _process_symbol(
        self, node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        is_public = not node.name.startswith("_")
        is_dunder = node.name.startswith("__") and node.name.endswith("__")
        if not (is_public and not is_dunder):
            return

        path_components = [*self.class_stack, node.name]
        symbol_path = f"{self.file_path}::{'.'.join(path_components)}"
        qualname = ".".join(path_components)

        module_name = (
            self.file_path.replace("src/", "").replace(".py", "").replace("/", ".")
        )
        kind_map = {
            "ClassDef": "class",
            "FunctionDef": "method" if self.class_stack else "function",
            "AsyncFunctionDef": "method" if self.class_stack else "function",
        }

        call_visitor = FunctionCallVisitor()
        call_visitor.visit(node)
        calls = sorted(list(call_visitor.calls))

        self.symbols.append(
            {
                "id": uuid.uuid5(uuid.NAMESPACE_DNS, symbol_path),
                "symbol_path": symbol_path,
                "module": module_name,
                "qualname": qualname,
                "kind": kind_map.get(type(node).__name__, "function"),
                "ast_signature": "pending",
                "fingerprint": calculate_structural_hash(node),
                "state": self._symbol_state(node),
                "is_public": True,
                "calls": json.dumps(calls),
            }
        )

    def _symbol_state(
        self, node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
    ) -> str:
        """ADR-151 D5: 'deprecated' for automatic-rule candidates.

        A symbol enters the dead-shim pipeline only when it (or its module)
        self-declares deprecation AND it is neither a property (D1 exclusion:
        attribute reads are not call edges) nor a dispatch registration
        (D2 grace: callers are graph-invisible). Everything else stays
        'discovered'.
        """
        dec_names = _decorator_names(node)
        if dec_names & _PROPERTY_DECORATORS or dec_names & _DISPATCH_DECORATORS:
            return "discovered"
        if self._module_deprecated or _self_declares_deprecated(node):
            return "deprecated"
        return "discovered"
