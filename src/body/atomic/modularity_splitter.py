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

        for mod in plan.modules:
            content = self._build_module(source, source_lines, tree, top_level, mod)
            target = package_path / f"{mod.module_name}.py"
            result.files.append((target, content))

            # __init__.py re-export line
            symbols_csv = ", ".join(mod.symbols)
            init_lines.append(f"from .{mod.module_name} import {symbols_csv}")

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
    ) -> str:
        """Compose the content for a single target module file."""
        # Validate that every symbol exists
        missing = [s for s in mod.symbols if s not in top_level]
        if missing:
            raise SplitPlanError(f"Symbols not found in source AST: {missing}")

        # Resolve imports
        import_lines = self._resolver.resolve(source, mod.symbols)

        # Extract symbol source text, preserving originals
        symbol_blocks: list[str] = []
        for sym_name in mod.symbols:
            node = top_level[sym_name]
            block = self._extract_node_source(node, source_lines)
            symbol_blocks.append(block)

        # Compose file
        parts: list[str] = []

        # Header comment
        parts.append(f"# {mod.module_name}.py")
        parts.append(f'"""{mod.rationale}"""')
        parts.append("")

        # Imports
        for imp in import_lines:
            parts.append(imp)
        if import_lines:
            parts.append("")
            parts.append("")

        # Symbol bodies
        parts.append("\n\n".join(symbol_blocks))
        parts.append("")  # trailing newline

        return "\n".join(parts)

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
