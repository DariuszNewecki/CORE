# src/mind/logic/engines/ast_gate/checks/purity_checks.py

"""
Purity Checks - Deterministic AST-based enforcement.

CONSTITUTIONAL FIX (V2.3.0):
- Modularized to reduce Modularity Debt (49.9 -> ~36.0).
- Delegated Path/Domain resolution to 'ASTHelpers'.
- Compressed 'Intelligence Layer' heuristics into data-driven patterns.
- Preserves all 7 distinct constitutional check types.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import ClassVar

from shared.infrastructure.intent.filesystem_operations import FsOperationTaxonomy

from ..base import ASTHelpers


# ID: 318924b3-cfe8-4ae2-a856-88deacf02a9b
class PurityChecks:
    """
    Stateless collection of purity and standard enforcement checks.

    Refactored to be a 'Thin Neuron' that delegates structural facts to ASTHelpers.
    """

    _ID_ANCHOR_PREFIXES: ClassVar[tuple[str, ...]] = ("# ID:",)

    @staticmethod
    # ID: d0d9b1d6-5849-486a-9f77-8333f4fd75a4
    def check_stable_id_anchor(source: str) -> list[str]:
        """Ensures all PUBLIC symbols have an '# ID:' anchor above them."""
        violations = []
        try:
            tree = ast.parse(source)
            lines = source.splitlines()
            for node in ast.walk(tree):
                if isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                ):
                    if node.name.startswith("_"):
                        continue

                    # Identifies line immediately above definition
                    idx = node.lineno - 2
                    if idx < 0 or not lines[idx].strip().startswith(
                        PurityChecks._ID_ANCHOR_PREFIXES
                    ):
                        violations.append(
                            f"Public symbol '{node.name}' missing stable ID anchor (line {node.lineno})."
                        )
        except Exception:
            pass
        return violations

    @staticmethod
    # ID: 4bd29d4a-63e7-4132-8ab2-16865c9d500c
    def check_docstrings_present(tree: ast.AST) -> list[str]:
        """Flags public functions and classes whose body lacks a docstring."""
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                child._parent = node  # type: ignore[attr-defined]

        violations: list[str] = []
        for node in ast.walk(tree):
            if not isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                continue
            if node.name.startswith("_"):
                continue
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                parent = getattr(node, "_parent", None)
                if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
            if ast.get_docstring(node) is None:
                kind = "Class" if isinstance(node, ast.ClassDef) else "Function"
                violations.append(
                    f"{kind} '{node.name}' has no docstring (line {node.lineno})."
                )
        return violations

    @staticmethod
    # ID: 1cc2a7f3-5e21-4c10-9f93-5d2b7bdb3a65
    def check_forbidden_decorators(tree: ast.AST, forbidden: list[str]) -> list[str]:
        """Prevents use of obsolete metadata decorators in source code."""
        violations, forbidden_set = [], {d.strip() for d in forbidden if d.strip()}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for dec in node.decorator_list:
                    name = ASTHelpers.full_attr_name(dec)
                    if name in forbidden_set:
                        violations.append(
                            f"Forbidden decorator '{name}' on '{node.name}' (line {ASTHelpers.lineno(dec)})."
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
        """Check for dangerous primitives (eval/exec) with trust-zone awareness.

        Matches both bare-name primitives (eval, exec) and dotted forms
        (os.system, subprocess.Popen). Bare-import forms (e.g.
        `from os import system; system(...)`) are also caught: callees are
        resolved through the import alias map and the qualified form is
        matched against the forbidden set. Closes the sibling of #488
        explicitly called out in governance_basics.yaml.
        """
        violations, forbidden_set = [], {p.strip() for p in forbidden if p.strip()}

        if file_path and allowed_domains:
            domain = ASTHelpers.extract_domain_from_path(file_path)
            if ASTHelpers.domain_matches(domain, allowed_domains):
                return []

        alias_map = ASTHelpers.build_import_alias_map(tree)
        for node in ast.walk(tree):
            name = None
            if isinstance(node, ast.Name):
                if node.id in forbidden_set:
                    name = node.id
                else:
                    # Bare-import resolution: `from os import system` makes
                    # Name("system") resolve to "os.system" via alias map.
                    resolved = alias_map.get(node.id)
                    if resolved and resolved in forbidden_set:
                        name = resolved
            elif isinstance(node, ast.Attribute):
                full = ASTHelpers.full_attr_name(node)
                if full in forbidden_set:
                    name = full
                else:
                    # Module-alias resolution: `import os as o; o.system()`
                    # resolves "o.system" -> "os.system".
                    resolved = ASTHelpers.resolve_qualified_name(node, alias_map)
                    if resolved and resolved != full and resolved in forbidden_set:
                        name = resolved

            if name:
                violations.append(
                    f"Forbidden primitive '{name}' used (line {ASTHelpers.lineno(node)})."
                )
        return violations

    @staticmethod
    # ID: 5425f58f-517d-4f2e-b0db-1c4638565b73
    def check_no_print_statements(tree: ast.AST) -> list[str]:
        """Enforces standard logging over print()."""
        return [
            f"Line {ASTHelpers.lineno(n)}: Replace print() with logger."
            for n in ast.walk(tree)
            if isinstance(n, ast.Call) and ASTHelpers.full_attr_name(n.func) == "print"
        ]

    @staticmethod
    # ID: a4b3c2d1-e0f9-8e7d-6c5b-4a3f2e1d0c9b
    def check_required_decorator(
        tree: ast.AST, decorator: str, file_path: Path | None = None, **kwargs
    ) -> list[str]:
        """Ensures state-modifying functions use governance decorators (e.g., @atomic_action)."""
        # SANCTUARY ZONE: Core infrastructure and low-level processors are exempt
        if file_path:
            p_str = str(file_path).replace("\\", "/")
            if any(
                x in p_str
                for x in [
                    "shared/infrastructure",
                    "shared/processors",
                    "repositories/db",
                ]
            ):
                return []

        violations = []
        # Heuristic: Functions with these tools/methods are considered 'Armed and Acting'
        mutating_tools = {"session", "db", "file_handler", "fs", "repo_path"}
        mutating_methods = {
            "write",
            "delete",
            "create",
            "save",
            "persist",
            "apply",
            "commit",
            "add",
            "update",
        }

        for fn in ast.walk(tree):
            if not isinstance(
                fn, (ast.FunctionDef, ast.AsyncFunctionDef)
            ) or fn.name.startswith(("_", "test_")):
                continue

            # 1. Tool Check (Arguments)
            args = {a.arg.lower() for a in [*fn.args.args, *fn.args.kwonlyargs]}
            if not any(t in args for t in mutating_tools):
                continue

            # 2. Action Check (Calls)
            is_acting = any(
                isinstance(c, ast.Call)
                and isinstance(c.func, ast.Attribute)
                and c.func.attr in mutating_methods
                for c in ast.walk(fn)
            )

            # 3. Decision: Flag if acting without the required decorator
            if is_acting and not any(
                ASTHelpers.full_attr_name(d) == decorator for d in fn.decorator_list
            ):
                violations.append(
                    f"Function '{fn.name}' appears state-modifying but lacks @{decorator} (line {fn.lineno})."
                )

        return violations

    @staticmethod
    # ID: 2dd7a4b8-fc4e-468e-9a1a-315acb2b3d6f
    def check_decorator_args(
        tree: ast.AST, decorator: str, required_args: list[str]
    ) -> list[str]:
        """Validates that specific decorators are called with mandatory keyword arguments."""
        violations, required_set = [], {a.strip() for a in required_args if a.strip()}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for dec in node.decorator_list:
                    if isinstance(dec, ast.Call):
                        if (
                            name := ASTHelpers.full_attr_name(dec.func)
                        ) == decorator or (name and name.split(".")[-1] == decorator):
                            present = {kw.arg for kw in dec.keywords if kw.arg}
                            missing = sorted(list(required_set - present))
                            if missing:
                                violations.append(
                                    f"@{decorator} on '{node.name}' missing required args {missing} (line {node.lineno})."
                                )
        return violations

    @staticmethod
    # ID: b7d320ba-ce8b-4274-8576-a254eeb58bd0
    def check_no_direct_writes(
        tree: ast.AST,
        taxonomy: FsOperationTaxonomy,
    ) -> list[str]:
        """Enforces the 'Governed Mutation Surface' by blocking raw filesystem writes.

        Derives the forbidden set from ``taxonomy.all_entries`` filtered by
        ``op_class == "write"``. Match mode is read per-entry from the
        taxonomy: ``leaf`` matches ``n.func.attr`` (catches the
        variable-receiver form, e.g. ``p.write_text()`` where ``p`` is a
        Path); ``qualified`` matches the dotted form recovered via
        ``ASTHelpers.resolve_qualified_name`` (collision-safe for ambiguous
        attribute names like ``replace`` and ``rename`` which would
        otherwise fire on ``str.replace`` and similar). The ``write_mode``
        predicate, when declared, filters ``open()`` to write/append modes
        via ``_is_write_mode``.

        Star imports and dynamic imports remain out of reach (#488). The
        variable-receiver bypass for the qualified-only leaves
        (``p.replace(...)``, ``p.rename(...)``) is a pre-existing,
        deliberately-accepted gap — leaf-match would collide with
        ``str.replace`` (143 src/ sites); see #489 migration trap.

        ADR-077 §6 step 3 convergence (#489) — replaces the previous
        hardcoded baseline + per-mapping ``forbidden_additional`` shape.
        """
        write_entries = [e for e in taxonomy.all_entries if e.op_class == "write"]
        leaf_entries = {e.name: e for e in write_entries if e.match == "leaf"}
        # Qualified-match detection is sourced from the watched block only.
        # pathlib_path qualified entries (`replace`, `rename`) exist for §3
        # completeness compliance; their bare leaf names would otherwise
        # match unrelated calls like `text.replace(...)` via
        # full_attr_name's fallback to `node.attr` for unresolvable value
        # chains. See #489 migration trap.
        qualified_entries = {
            e.name: e
            for e in write_entries
            if e.match == "qualified" and e.namespace == "watched"
        }

        alias_map = ASTHelpers.build_import_alias_map(tree)
        violations: list[str] = []

        for n in ast.walk(tree):
            if not isinstance(n, ast.Call):
                continue

            attr_leaf = n.func.attr if isinstance(n.func, ast.Attribute) else None
            qualified = ASTHelpers.resolve_qualified_name(n.func, alias_map)

            candidates: list[tuple[str, str]] = []
            if attr_leaf and attr_leaf in leaf_entries:
                candidates.append((leaf_entries[attr_leaf].predicate or "", attr_leaf))
            if qualified and qualified in qualified_entries:
                candidates.append(
                    (qualified_entries[qualified].predicate or "", qualified)
                )

            for predicate, display in candidates:
                if predicate == "write_mode" and not _is_write_mode(n):
                    continue
                violations.append(
                    f"Direct write detected: '{display}' "
                    f"(line {ASTHelpers.lineno(n)}). Use FileHandler."
                )
                break

        return violations

    @staticmethod
    # ID: f3a1c2d4-7e8b-4f9a-b6c5-2d3e4f5a6b7c
    def check_forbidden_imports_and_calls(
        tree: ast.AST,
        forbidden_imports: list[str],
        forbidden_calls: list[str],
    ) -> list[str]:
        """
        Enforces architecture.channels rules by blocking terminal-rendering primitives
        in non-UI modules.

        Detects:
        - Forbidden module imports (e.g. 'rich.console', 'rich.table')
        - Forbidden call expressions (e.g. 'Console()', 'console.print()', 'Table()')
        """
        violations: list[str] = []
        forbidden_import_set = {m.strip() for m in forbidden_imports if m.strip()}
        forbidden_call_set = {c.strip() for c in forbidden_calls if c.strip()}

        for node in ast.walk(tree):
            # Check imports: `import rich.console` or `from rich.console import ...`
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in forbidden_import_set:
                        violations.append(
                            f"Line {node.lineno}: Forbidden import '{alias.name}'."
                        )
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module in forbidden_import_set:
                    violations.append(
                        f"Line {node.lineno}: Forbidden import-from '{node.module}'."
                    )

            # Check calls: Console(), console.print(), Table(), etc.
            elif isinstance(node, ast.Call):
                name = ASTHelpers.full_attr_name(node.func)
                if name in forbidden_call_set:
                    violations.append(
                        f"Line {ASTHelpers.lineno(node)}: Forbidden call '{name}()'."
                    )

        return violations

    _TEMPFILE_REQUIRES_DIR: ClassVar[frozenset[str]] = frozenset(
        {
            "tempfile.TemporaryDirectory",
            "tempfile.NamedTemporaryFile",
            "tempfile.mkdtemp",
            "tempfile.mkstemp",
        }
    )
    _TEMPFILE_FORBIDDEN: ClassVar[frozenset[str]] = frozenset({"tempfile.gettempdir"})

    @staticmethod
    # ID: 3b685f57-0f85-4e12-b21d-d86a9d76bd41
    def check_tempfile_default_dir(tree: ast.AST) -> list[str]:
        """Detect tempfile.* calls that resolve to /tmp/.

        Without an explicit `dir=` kwarg, tempfile.TemporaryDirectory,
        NamedTemporaryFile, mkdtemp, and mkstemp fall through to
        tempfile.gettempdir(), which is /tmp/ on Linux — prohibited by
        CLAUDE.md. tempfile.gettempdir() is forbidden outright.

        The check only verifies that `dir=` is *present*; the kwarg's value
        is not statically validated. This is sound for the four real-world
        siblings closed by #508 and matches how other purity rules trust
        present-but-unverified kwargs (e.g. write_defaults_false).
        """
        violations: list[str] = []
        alias_map = ASTHelpers.build_import_alias_map(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            callee = ASTHelpers.full_attr_name(node.func)
            resolved = ASTHelpers.resolve_qualified_name(node.func, alias_map) or callee
            if resolved in PurityChecks._TEMPFILE_FORBIDDEN:
                violations.append(
                    f"Line {ASTHelpers.lineno(node)}: '{resolved}()' is forbidden — "
                    "the system temp dir is prohibited by CLAUDE.md; use an explicit "
                    "repo-internal path under var/tmp/ instead."
                )
            elif resolved in PurityChecks._TEMPFILE_REQUIRES_DIR:
                has_dir_kwarg = any(kw.arg == "dir" for kw in node.keywords)
                if not has_dir_kwarg:
                    violations.append(
                        f"Line {ASTHelpers.lineno(node)}: '{resolved}' must pass an "
                        "explicit `dir=` keyword pointing under repo_root/var/tmp/ "
                        "(CLAUDE.md /tmp/ prohibition)."
                    )
        return violations


def _is_write_mode(node: ast.Call) -> bool:
    """Internal helper to detect 'w' or 'a' in file open() calls."""
    # Check positional arguments and keyword 'mode' argument
    for arg in node.args + [k.value for k in node.keywords if k.arg == "mode"]:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            if any(m in arg.value for m in "wa"):
                return True
    return False
