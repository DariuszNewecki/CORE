# src/shared/utils/public_symbols.py
"""
The public testable symbols of a Python module — one definition.

ADR-133 D2: the autonomous test pipeline tests public symbols — public
module-level functions and classes, and the public, non-dunder methods of
public classes. TestGapEvaluator (body) uses this to find untested symbols;
the coverage scan (shared, test_coverage.yaml ``exempt_modules_without_public_symbols``)
uses it to exempt modules that have none (governor ruling 2026-10-03). Both
import it from here so the two cannot diverge.

Pure AST: no imports of the module, no I/O beyond reading the file.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


# Dunders never treated as separately testable methods.
DUNDER_SKIP: frozenset[str] = frozenset(
    {
        "__init__",
        "__repr__",
        "__str__",
        "__eq__",
        "__hash__",
        "__lt__",
        "__le__",
        "__gt__",
        "__ge__",
        "__len__",
        "__bool__",
        "__enter__",
        "__exit__",
        "__aenter__",
        "__aexit__",
        "__iter__",
        "__next__",
        "__contains__",
        "__getitem__",
        "__setitem__",
        "__delitem__",
    }
)


@dataclass(frozen=True)
# ID: bedf5eef-fd56-4b3f-8a7e-46b1828ecba8
class PublicSymbol:
    """One public testable symbol: name (``Class.method`` for methods), kind, signature."""

    name: str
    kind: str
    signature: str


# ID: 5ce6649c-ba41-41d6-9d40-a016e31d4626
def extract_public_symbols(source_path: Path) -> list[PublicSymbol]:
    """Public module-level functions, classes and class methods, via AST.

    Raises ``SyntaxError`` when the source cannot be parsed.
    """
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(source_path))
    symbols: list[PublicSymbol] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                symbols.append(
                    PublicSymbol(node.name, "function", _format_signature(node))
                )
        elif isinstance(node, ast.ClassDef):
            if not node.name.startswith("_"):
                symbols.append(PublicSymbol(node.name, "class", f"class {node.name}"))
                for child in ast.iter_child_nodes(node):
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if (
                            not child.name.startswith("_")
                            and child.name not in DUNDER_SKIP
                        ):
                            symbols.append(
                                PublicSymbol(
                                    f"{node.name}.{child.name}",
                                    "method",
                                    _format_signature(child),
                                )
                            )
    return symbols


# ID: a409feeb-325a-4591-8395-9f24f1cf94b5
def has_public_testable_symbols(source_path: Path) -> bool:
    """True when the module has at least one public testable symbol.

    A module that cannot be parsed counts as having symbols: an unreadable
    module is never exempted from the test-file requirement.
    """
    try:
        return bool(extract_public_symbols(source_path))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return True


def _format_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args = [arg.arg for arg in node.args.args]
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    return f"{prefix} {node.name}({', '.join(args)})"
