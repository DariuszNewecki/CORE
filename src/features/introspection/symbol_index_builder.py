# src/features/introspection/symbol_index_builder.py
"""Provides functionality for the symbol_index_builder module."""

from __future__ import annotations

import ast
import json
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


# Optional dependency (PyYAML). If missing, we fall back to a tiny default set.
try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # type: ignore


@dataclass
# ID: 39b26f28-006c-487b-ba6b-648c2a0942ca
class Pattern:
    name: str
    description: str
    match: dict[str, Any]
    entry_point_type: str


@dataclass
# ID: 7f417874-2248-4eb1-9b33-65eaf7abf457
class SymbolMeta:
    key: str
    filepath: str
    name: str
    type: str  # "function" | "class" | "method"
    base_classes: list[str]
    decorators: list[str]
    is_public_function: bool
    module_path: str


def _load_patterns(patterns_path: Path) -> list[Pattern]:
    if yaml is None:
        # Minimal safe fallback if PyYAML is not present
        default_patterns = [
            {
                "name": "typer_cli_command",
                "description": "Public functions in src/cli/ are CLI commands.",
                "match": {
                    "type": "function",
                    "is_public_function": True,
                    "module_path_contains": "src/cli/",
                },
                "entry_point_type": "cli_command",
            },
            {
                "name": "sqlalchemy_orm_model",
                "description": "ORM models count as data models.",
                "match": {
                    "type": "class",
                    "module_path_contains": "src/services/database/models",
                },
                "entry_point_type": "data_model",
            },
        ]
        return [Pattern(**p) for p in default_patterns]

    data = yaml.safe_load(patterns_path.read_text(encoding="utf-8"))
    items = data.get("patterns", []) if isinstance(data, dict) else []
    out: list[Pattern] = []
    for p in items:
        out.append(
            Pattern(
                name=p.get("name", ""),
                description=p.get("description", ""),
                match=p.get("match", {}) or {},
                entry_point_type=p.get("entry_point_type", ""),
            )
        )
    return out


def _iter_py_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*.py"):
        # Skip venvs and reports etc.
        s = str(p.as_posix())
        if "/.venv/" in s or "/venv/" in s or "/.git/" in s or s.startswith("reports/"):
            continue
        yield p


class _Visitor(ast.NodeVisitor):
    def __init__(self, filepath: Path) -> None:
        self.filepath = filepath
        self.module_path = filepath.as_posix()
        self.symbols: list[SymbolMeta] = []
        self._class_stack: list[ast.ClassDef] = []

    # ID: 88f6a80e-1874-4c28-8240-f80c53509d16
    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        bases = [self._name_of(b) for b in node.bases]
        decorators = [self._name_of(d) for d in node.decorator_list]
        meta = SymbolMeta(
            key=f"{self.module_path}::{node.name}",
            filepath=self.module_path,
            name=node.name,
            type="class",
            base_classes=bases,
            decorators=decorators,
            is_public_function=not node.name.startswith("_"),
            module_path=self.module_path,
        )
        self.symbols.append(meta)

        self._class_stack.append(node)
        self.generic_visit(node)
        self._class_stack.pop()
        return None

    # ID: 28ae72fd-9693-4cf8-91a8-c5e857f717c3
    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self._handle_function_like(node)
        return None

    # ID: 806bb60a-67a0-4b27-bbe4-f0960c19da1d
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        self._handle_function_like(node)
        return None

    def _handle_function_like(self, node: ast.AST) -> None:
        name = getattr(node, "name", "<unknown>")
        decorators = [self._name_of(d) for d in getattr(node, "decorator_list", [])]
        bases: list[str] = []
        sym_type = "method" if self._class_stack else "function"
        if self._class_stack:
            # include base classes of the owning class (helpful for ActionHandler match)
            owner = self._class_stack[-1]
            bases = [self._name_of(b) for b in owner.bases]

        meta = SymbolMeta(
            key=f"{self.module_path}::{self._qualified_name(name)}",
            filepath=self.module_path,
            name=name,
            type=sym_type,
            base_classes=bases,
            decorators=decorators,
            is_public_function=not name.startswith("_"),
            module_path=self.module_path,
        )
        self.symbols.append(meta)

    def _qualified_name(self, name: str) -> str:
        if self._class_stack:
            return f"{self._class_stack[-1].name}.{name}"
        return name

    @staticmethod
    def _name_of(node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return _Visitor._name_of(node.value) + "." + node.attr
        if isinstance(node, ast.Subscript):
            return _Visitor._name_of(node.value)
        try:
            return ast.unparse(node)  # py3.9+
        except Exception:
            return node.__class__.__name__


def _match_pattern(sym: SymbolMeta, pat: Pattern) -> bool:
    m = pat.match
    # type match
    if "type" in m:
        if m["type"] == "function" and sym.type not in {"function", "method"}:
            return False
        if m["type"] == "class" and sym.type != "class":
            return False

    # module path contains
    if "module_path_contains" in m:
        if m["module_path_contains"] not in sym.module_path:
            return False

    # name regex
    if "name_regex" in m:
        if not re.search(m["name_regex"], sym.name):
            # also allow Class.method part if present
            qn = sym.key.split("::", 1)[-1]
            if not re.search(m["name_regex"], qn):
                return False

    # is_public_function
    if "is_public_function" in m:
        want_pub = bool(m["is_public_function"])
        if sym.type in {"function", "method"}:
            if sym.is_public_function != want_pub:
                return False

    # base_class_includes
    if "base_class_includes" in m:
        needed = str(m["base_class_includes"])
        if not any(needed in b for b in sym.base_classes):
            return False

    # has_decorator
    if "has_decorator" in m:
        need = str(m["has_decorator"])
        if not any(need in d for d in sym.decorators):
            return False

    # has_capability_tag (best-effort: look for '# ID:' above def/class)
    if m.get("has_capability_tag"):
        # We will scan the file quickly: if '# ID:' appears on the same line
        # as the def/class or just above it, consider it tagged.
        try:
            source = Path(sym.filepath).read_text(encoding="utf-8").splitlines()
            # find line number by searching name; best-effort
            for i, line in enumerate(source, 1):
                if f"def {sym.name}" in line or f"class {sym.name}" in line:
                    window = "\n".join(source[max(0, i - 4) : i + 1])
                    if "# ID" in window or "#ID" in window:
                        break
            else:
                return False
        except Exception:
            return False

    return True


def _classify(
    symbols: list[SymbolMeta], patterns: list[Pattern]
) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for s in symbols:
        ep_type = None
        pat_name = None
        just = None
        for p in patterns:
            if _match_pattern(s, p):
                ep_type = p.entry_point_type or None
                pat_name = p.name or None
                just = p.description or None
                break

        index[s.key] = {
            "entry_point_type": ep_type,
            "pattern_name": pat_name,
            "entry_point_justification": just,
        }
    return index


# ID: 47559b4a-19e6-4ef4-ba52-4951fe0346ec
def build_symbol_index(
    project_root: str | Path = ".",
    patterns_path: str | Path = ".intent/mind/knowledge/entry_point_patterns.yaml",
    src_dir: str | Path = "src",
) -> dict[str, dict[str, Any]]:
    root = Path(project_root).resolve()
    src = (root / src_dir).resolve()
    patterns_file = (root / patterns_path).resolve()

    if not patterns_file.exists():
        raise FileNotFoundError(f"Entry point patterns not found: {patterns_file}")

    patterns = _load_patterns(patterns_file)
    all_symbols: list[SymbolMeta] = []

    for py in _iter_py_files(src):
        try:
            text = py.read_text(encoding="utf-8")
        except Exception:
            continue
        try:
            tree = ast.parse(text)
        except Exception:
            continue
        v = _Visitor(py)
        v.visit(tree)
        all_symbols.extend(v.symbols)

    return _classify(all_symbols, patterns)


# ID: 04b011a8-a32a-42b9-a42b-3f27b5226db0
def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Build symbol_index.json from AST + patterns."
    )
    parser.add_argument("--project-root", default=".", help="Project root (default: .)")
    parser.add_argument(
        "--patterns",
        default=".intent/mind/knowledge/entry_point_patterns.yaml",
        help="Patterns YAML path",
    )
    parser.add_argument("--src", default="src", help="Source directory (default: src)")
    parser.add_argument(
        "--out", default="reports/symbol_index.json", help="Output JSON path"
    )
    args = parser.parse_args(argv or sys.argv[1:])

    index = build_symbol_index(args.project_root, args.patterns, args.src)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    # FUTURE: Replace with logging once logger is configured
    # print(f"Wrote {out_path.as_posix()} with {len(index)} symbols.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
