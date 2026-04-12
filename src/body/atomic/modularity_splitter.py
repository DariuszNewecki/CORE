# src/body/atomic/modularity_splitter.py

"""
Deterministic modularization splitter.

Given a source file and a validated SplitPlan, produces a SplitResult
describing every file that *would* be written — without writing anything.
The Execution phase decides whether to persist.

Constitutional note:
  Body layer — read-only.  SplitResult is a proposal, not an action.
  No settings access, no file writes.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

from body.atomic.import_resolver import ImportResolver
from body.atomic.split_plan import ModuleSpec, SplitPlan, SplitPlanError
from shared.logger import getLogger


logger = getLogger(__name__)


@dataclass
# ID: 9b77fadf-6869-44bd-a1fd-12a8f24d830c
class SplitResult:
    """Describes the files a modularization split would produce."""

    files: list[tuple[Path, str]] = field(default_factory=list)
    original_path: Path = field(default_factory=lambda: Path())
    package_path: Path = field(default_factory=lambda: Path())


# ID: 6a9c0d1e-2f3b-4c5d-8e7f-0a1b2c3d4e5f
class ModularitySplitter:
    """Split a single source file into a package according to a SplitPlan.

    All work is AST-based and deterministic.  The returned SplitResult
    contains *proposed* file contents; nothing is written to disk.
    """

    def __init__(self) -> None:
        self._resolver = ImportResolver()

    # ID: 4e7f8a9b-0c1d-2e3f-4a5b-6c7d8e9f0a1b
    def split(self, source_path: Path, plan: SplitPlan) -> SplitResult:
        """Produce a SplitResult from *source_path* and a validated *plan*.

        Parameters
        ----------
        source_path:
            Absolute path to the file being split.
        plan:
            A validated ``SplitPlan`` (caller must have called ``validate()``).

        Returns
        -------
        SplitResult
            Proposed files.  Nothing is written to disk.

        Raises
        ------
        SplitPlanError
            If a symbol listed in the plan cannot be found in the source AST.
        """
        source = source_path.read_text(encoding="utf-8")
        source_lines = source.splitlines(keepends=True)
        tree = ast.parse(source)

        package_path = source_path.parent / plan.new_package_name

        # Build name → AST-node index for top-level definitions
        top_level: dict[str, ast.stmt] = {}
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                top_level[node.name] = node

        # Also index top-level assignments (constants, module-level vars)
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        top_level[target.id] = node

        # Second indexing pass: detect the single-dominant-class case.
        # If one top-level ClassDef contains more than half the total symbols
        # in the plan, build a method-name → AST-node index for that class.
        class_methods: dict[str, ast.stmt] = {}
        dominant_class_name: str | None = None
        class_defs = [
            n for n in ast.iter_child_nodes(tree) if isinstance(n, ast.ClassDef)
        ]
        total_plan_symbols = sum(len(m.symbols) for m in plan.modules)
        if class_defs and total_plan_symbols > 0:
            largest = max(
                class_defs,
                key=lambda c: sum(
                    1
                    for n in c.body
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                ),
            )
            largest_method_count = sum(
                1
                for n in largest.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            )
            if 2 * largest_method_count > total_plan_symbols:
                dominant_class_name = largest.name
                for member in largest.body:
                    if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        class_methods[member.name] = member
                    elif isinstance(member, ast.AnnAssign) and isinstance(
                        member.target, ast.Name
                    ):
                        class_methods[member.target.id] = member
                    elif isinstance(member, ast.Assign):
                        for target in member.targets:
                            if isinstance(target, ast.Name):
                                class_methods[target.id] = member

        is_class_split_plan = any(m.is_class_split for m in plan.modules)

        # Build symbol → module_name map for cross-module resolution
        symbol_to_module: dict[str, str] = {}
        for mod in plan.modules:
            for sym in mod.symbols:
                symbol_to_module[sym] = mod.module_name

        # Collect all module-level assignment names from original source
        module_assigns: set[str] = set()
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        module_assigns.add(target.id)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                module_assigns.add(node.target.id)

        result = SplitResult(
            files=[],
            original_path=source_path,
            package_path=package_path,
        )

        init_lines: list[str] = [
            f"# {plan.new_package_name}/__init__.py",
            '"""',
            f"Package split from {source_path.name}.",
            '"""',
            "",
            "from __future__ import annotations",
            "",
        ]

        # ----- class-split branch ----------------------------------------
        if is_class_split_plan:
            # Order modules so that the one containing __init__ comes first;
            # multiple inheritance MRO will use its constructor.
            primary_idx = next(
                (i for i, m in enumerate(plan.modules) if "__init__" in m.symbols),
                0,
            )
            ordered = [plan.modules[primary_idx]] + [
                m for i, m in enumerate(plan.modules) if i != primary_idx
            ]

            parent_classes: list[str] = []
            for mod in ordered:
                content = self._build_module(
                    source,
                    source_lines,
                    tree,
                    top_level,
                    mod,
                    symbol_to_module,
                    class_methods=class_methods,
                )
                target = package_path / f"{mod.module_name}.py"
                result.files.append((target, content))

                class_name = self._to_title_case(mod.module_name)
                init_lines.append(f"from .{mod.module_name} import {class_name}")
                parent_classes.append(class_name)

            # Re-export the original class name for backward compatibility
            # by composing the new per-module classes via multiple inheritance.
            if dominant_class_name and parent_classes:
                init_lines.append("")
                init_lines.append("")
                init_lines.append(
                    f"class {dominant_class_name}({', '.join(parent_classes)}):"
                )
                init_lines.append("    pass")

            init_lines.append("")  # trailing newline
            result.files.append((package_path / "__init__.py", "\n".join(init_lines)))
            return result

        # ----- regular (top-level symbol) branch -------------------------
        plan_symbols: set[str] = set()
        for mod in plan.modules:
            plan_symbols.update(mod.symbols)

        # Track which module first includes each module-level assignment
        assign_to_first_module: dict[str, str] = {}

        for mod in plan.modules:
            content = self._build_module(
                source, source_lines, tree, top_level, mod, symbol_to_module
            )
            target = package_path / f"{mod.module_name}.py"
            result.files.append((target, content))

            # __init__.py re-export line for plan symbols
            symbols_csv = ", ".join(mod.symbols)
            init_lines.append(f"from .{mod.module_name} import {symbols_csv}")

            # Track module-level assigns referenced by this module's symbols
            refs = self._collect_all_refs(top_level, mod.symbols)
            for assign_name in module_assigns:
                if (
                    assign_name in refs
                    and assign_name not in plan_symbols
                    and assign_name not in assign_to_first_module
                ):
                    assign_to_first_module[assign_name] = mod.module_name

        # Re-export public module-level assignments in __init__.py
        reexport_by_module: dict[str, list[str]] = {}
        for name, mod_name in assign_to_first_module.items():
            if not name.startswith("_"):
                reexport_by_module.setdefault(mod_name, []).append(name)

        for mod_name, names in sorted(reexport_by_module.items()):
            init_lines.append(f"from .{mod_name} import {', '.join(sorted(names))}")

        init_lines.append("")  # trailing newline
        result.files.append((package_path / "__init__.py", "\n".join(init_lines)))

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_module(
        self,
        source: str,
        source_lines: list[str],
        tree: ast.Module,
        top_level: dict[str, ast.stmt],
        mod: ModuleSpec,
        symbol_to_module: dict[str, str],
        *,
        class_methods: dict[str, ast.stmt] | None = None,
    ) -> str:
        """Compose the content for a single target module file."""
        # Branch on is_class_split BEFORE choosing which index to use.
        if mod.is_class_split:
            symbol_index: dict[str, ast.stmt] = class_methods or {}
        else:
            symbol_index = top_level

        # Validate that every symbol exists in the chosen index
        missing = [s for s in mod.symbols if s not in symbol_index]
        if missing:
            raise SplitPlanError(f"Symbols not found in source AST: {missing}")

        # Resolve imports
        if mod.is_class_split:
            method_nodes = [symbol_index[s] for s in mod.symbols]
            import_lines = self._resolve_imports_for_methods(source, method_nodes)
            # Methods reach each other via ``self.x``; no relative imports
            cross_import_lines: list[str] = []
        else:
            import_lines = self._resolver.resolve(source, mod.symbols)

            # Compute cross-module imports for symbols in other split modules
            cross_imports: dict[str, set[str]] = {}
            for sym_name in mod.symbols:
                node = top_level[sym_name]
                for child in ast.walk(node):
                    if isinstance(child, ast.Name) and child.id in symbol_to_module:
                        other_mod = symbol_to_module[child.id]
                        if other_mod != mod.module_name:
                            cross_imports.setdefault(other_mod, set()).add(child.id)

            cross_import_lines = []
            for other_mod, syms in sorted(cross_imports.items()):
                cross_import_lines.append(
                    f"from .{other_mod} import {', '.join(sorted(syms))}"
                )

        # Extract symbol source text, preserving originals
        symbol_blocks: list[str] = []
        for sym_name in mod.symbols:
            node = symbol_index[sym_name]
            block = self._extract_node_source(node, source_lines)
            symbol_blocks.append(block)

        # Compose file
        parts: list[str] = []

        # Header comment
        parts.append(f"# {mod.module_name}.py")
        parts.append(f'"""{mod.rationale}"""')
        parts.append("")

        # External imports + module-level assignments
        for imp in import_lines:
            parts.append(imp)

        # Cross-module relative imports
        if cross_import_lines:
            if import_lines:
                parts.append("")
            for line in cross_import_lines:
                parts.append(line)

        if import_lines or cross_import_lines:
            parts.append("")
            parts.append("")

        # Symbol bodies — wrap in a class for class splits, otherwise emit
        # them as top-level definitions.
        if mod.is_class_split:
            class_name = self._to_title_case(mod.module_name)
            parts.append(f"class {class_name}:")
            # Methods are already indented for class scope in the original
            # source, so we keep their text verbatim.
            parts.append("\n\n".join(symbol_blocks))
        else:
            parts.append("\n\n".join(symbol_blocks))
        parts.append("")  # trailing newline

        return "\n".join(parts)

    @staticmethod
    def _to_title_case(snake: str) -> str:
        """Convert ``snake_case`` → ``TitleCase``."""
        return "".join(part.capitalize() for part in snake.split("_") if part)

    def _resolve_imports_for_methods(
        self, source: str, method_nodes: list[ast.stmt]
    ) -> list[str]:
        """Resolve minimal imports needed by a set of class method nodes.

        Mirrors :meth:`ImportResolver.resolve` but starts from arbitrary AST
        nodes rather than top-level symbol names — required for class splits
        where the "symbols" are methods nested inside a ClassDef.
        """
        tree = ast.parse(source)
        source_lines = source.splitlines(keepends=True)

        # Collect top-level imports and any TYPE_CHECKING block
        import_nodes: list[ast.stmt] = []
        type_checking_block: list[ast.stmt] = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                import_nodes.append(node)
            elif isinstance(node, ast.If) and self._resolver._is_type_checking_guard(
                node
            ):
                type_checking_block.append(node)

        # Module-level assignments
        module_assigns: dict[str, ast.stmt] = {}
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        module_assigns[target.id] = node
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                module_assigns[node.target.id] = node

        # Classify imports
        future_imports: list[str] = []
        regular_imports: list[tuple[ast.stmt, str]] = []
        for node in import_nodes:
            stmt_text = self._resolver._node_source(node, source_lines)
            if isinstance(node, ast.ImportFrom) and node.module == "__future__":
                future_imports.append(stmt_text)
            else:
                regular_imports.append((node, stmt_text))

        # Names referenced by the method bodies
        needed_names: set[str] = set()
        for mnode in method_nodes:
            for child in ast.walk(mnode):
                if isinstance(child, ast.Name):
                    needed_names.add(child.id)
                elif isinstance(child, ast.Attribute):
                    root = self._resolver._attribute_root(child)
                    if root:
                        needed_names.add(root)

        # Module-level assignments referenced by the method bodies
        needed_assigns: dict[str, ast.stmt] = {}
        for name, node in module_assigns.items():
            if name in needed_names:
                needed_assigns[name] = node
        for node in needed_assigns.values():
            for child in ast.walk(node):
                if isinstance(child, ast.Name):
                    needed_names.add(child.id)
                elif isinstance(child, ast.Attribute):
                    root = self._resolver._attribute_root(child)
                    if root:
                        needed_names.add(root)

        # Match regular imports against expanded needed-name set
        matched: list[str] = []
        for node, stmt_text in regular_imports:
            if self._resolver._import_provides(node, needed_names):
                matched.append(stmt_text)

        result: list[str] = list(future_imports)
        if type_checking_block:
            for block_node in type_checking_block:
                result.append(self._resolver._node_source(block_node, source_lines))
        result.extend(matched)

        seen_lines: set[int] = set()
        for node in needed_assigns.values():
            if node.lineno not in seen_lines:
                result.append("")
                result.append(self._resolver._node_source(node, source_lines))
                seen_lines.add(node.lineno)

        return result

    @staticmethod
    def _collect_all_refs(
        top_level: dict[str, ast.stmt], symbol_names: list[str]
    ) -> set[str]:
        """Collect all Name references from the bodies of *symbol_names*."""
        refs: set[str] = set()
        for sym_name in symbol_names:
            node = top_level.get(sym_name)
            if node is None:
                continue
            for child in ast.walk(node):
                if isinstance(child, ast.Name):
                    refs.add(child.id)
        return refs

    def _extract_node_source(self, node: ast.stmt, source_lines: list[str]) -> str:
        """Extract the original source text of *node* including leading comments.

        Preserves ``# ID:`` anchors that appear on the line before the
        definition — required by the constitutional symbol-ID rule.
        """
        start = node.lineno - 1  # 0-based
        end = node.end_lineno if node.end_lineno is not None else node.lineno

        # Look backwards for comment lines attached to this definition
        # (e.g. ``# ID: ...`` or docstring preamble comments).
        while start > 0 and source_lines[start - 1].strip().startswith("#"):
            start -= 1

        return "".join(source_lines[start:end]).rstrip()
