# src/features/introspection/symbol_index_builder.py
"""
Builds symbol_index.json from AST + patterns.

CONSTITUTIONAL FIX:
- Aligned with 'governance.artifact_mutation.traceable'.
- Aligned with 'logic.logging.standard_only' (removed print statements).
- Replaced direct Path writes with governed FileHandler mutations.
- Fixed syntax error and ensured Python 3.12 compatibility.
"""

from __future__ import annotations

import ast
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# REFACTORED: Removed direct settings import
from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger


logger = getLogger(__name__)

try:
    import yaml
except Exception:
    yaml = None


@dataclass
# ID: 3599bcdc-f7c4-4ee8-94f1-c30cf63c7104
class Pattern:
    name: str
    description: str
    match: dict[str, Any]
    entry_point_type: str


@dataclass
# ID: b9f1867b-96ed-4fe0-b382-6ebea7d5500f
class SymbolMeta:
    key: str
    filepath: str
    name: str
    type: str  # function | class | method
    base_classes: list[str]
    decorators: list[str]
    is_public_function: bool
    module_path: str


def _load_patterns(patterns_path: Path) -> list[Pattern]:
    if yaml is None or not patterns_path.exists():
        return [
            Pattern(
                name="cli_command",
                description="CLI entry points",
                match={"type": "function", "module_path_contains": "src/cli/"},
                entry_point_type="cli_command",
            )
        ]

    data = yaml.safe_load(patterns_path.read_text(encoding="utf-8"))
    items = data.get("patterns", []) if isinstance(data, dict) else []
    return [
        Pattern(
            name=p.get("name", ""),
            description=p.get("description", ""),
            match=p.get("match", {}) or {},
            entry_point_type=p.get("entry_point_type", ""),
        )
        for p in items
    ]


def _iter_py_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*.py"):
        s = str(p.as_posix())
        if any(x in s for x in ["/.venv/", "/venv/", "/.git/", "reports/"]):
            continue
        yield p


class _Visitor(ast.NodeVisitor):
    def __init__(self, filepath: Path) -> None:
        self.filepath = filepath
        self.module_path = filepath.as_posix()
        self.symbols: list[SymbolMeta] = []
        self._class_stack: list[ast.ClassDef] = []

    # ID: 53ffac44-279f-475f-8479-85ae61fbf17b
    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        bases = [self._name_of(b) for b in node.bases]
        decorators = [self._name_of(d) for d in node.decorator_list]
        self.symbols.append(
            SymbolMeta(
                key=f"{self.module_path}::{node.name}",
                filepath=self.module_path,
                name=node.name,
                type="class",
                base_classes=bases,
                decorators=decorators,
                is_public_function=not node.name.startswith("_"),
                module_path=self.module_path,
            )
        )
        self._class_stack.append(node)
        self.generic_visit(node)
        self._class_stack.pop()

    # ID: 50c1acc1-14b2-4998-8741-aa255b1fa719
    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self._handle_func(node)

    # ID: 8adec9fb-254d-4d09-896a-0155fcce78bf
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        self._handle_func(node)

    def _handle_func(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        name = node.name
        decorators = [self._name_of(d) for d in node.decorator_list]
        bases: list[str] = []
        if self._class_stack:
            bases = [self._name_of(b) for b in self._class_stack[-1].bases]

        self.symbols.append(
            SymbolMeta(
                key=f"{self.module_path}::{self._qn(name)}",
                filepath=self.module_path,
                name=name,
                type="method" if self._class_stack else "function",
                base_classes=bases,
                decorators=decorators,
                is_public_function=not name.startswith("_"),
                module_path=self.module_path,
            )
        )

    def _qn(self, name: str) -> str:
        return f"{self._class_stack[-1].name}.{name}" if self._class_stack else name

    def _name_of(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return f"{self._name_of(node.value)}.{node.attr}"
        try:
            return ast.unparse(node)
        except Exception:
            return "unknown"


def _match_pattern(sym: SymbolMeta, pat: Pattern) -> bool:
    m = pat.match
    if "type" in m:
        if m["type"] == "function" and sym.type not in {"function", "method"}:
            return False
        if m["type"] == "class" and sym.type != "class":
            return False
    if "module_path_contains" in m and m["module_path_contains"] not in sym.module_path:
        return False
    if "name_regex" in m and not re.search(m["name_regex"], sym.name):
        return False
    return True


def _classify(symbols: list[SymbolMeta], patterns: list[Pattern]) -> dict[str, dict]:
    index = {}
    for s in symbols:
        for p in patterns:
            if _match_pattern(s, p):
                index[s.key] = {
                    "entry_point_type": p.entry_point_type,
                    "pattern_name": p.name,
                    "entry_point_justification": p.description,
                }
                break
    return index


# ID: 2e550e18-7c09-4ccc-a967-e1d38fac6f8f
def build_symbol_index(
    project_root: str | Path = ".",
    patterns_path: str | Path = ".intent/mind/knowledge/entry_point_patterns.yaml",
) -> dict[str, dict]:
    root = Path(project_root).resolve()
    src = root / "src"
    patterns_file = root / patterns_path

    if not patterns_file.exists():
        # Degrade gracefully if patterns are missing
        patterns = []
    else:
        patterns = _load_patterns(patterns_file)

    all_symbols: list[SymbolMeta] = []
    for py in _iter_py_files(src):
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
            visitor = _Visitor(py)
            visitor.visit(tree)
            all_symbols.extend(visitor.symbols)
        except Exception:
            continue

    return _classify(all_symbols, patterns)


# ID: aeb56496-e95c-4537-aeb7-81ca8b3a9372
def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Build symbol index.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--out", default="reports/symbol_index.json")
    args = parser.parse_args(argv or sys.argv[1:])

    try:
        project_root = Path(args.project_root).resolve()
        index = build_symbol_index(args.project_root)
        fh = FileHandler(str(project_root))

        # Resolve output path
        out_path = Path(args.out)
        repo_abs = project_root

        if out_path.is_absolute():
            rel_output = str(out_path.relative_to(repo_abs))
        else:
            rel_output = str(out_path).replace("\\", "/")

        fh.write_runtime_json(rel_output, index)
        return 0
    except Exception as e:
        # CONSTITUTIONAL FIX: Replace print with logger.error
        logger.error("Failed to build symbol index: %s", e, exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
