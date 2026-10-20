# src/shared/utils/public_symbols.py
"""
The public testable symbols of a Python module — one definition.

ADR-133 D2: the autonomous test pipeline tests public symbols — public
module-level functions and classes, and the public, non-dunder methods of
public classes. TestGapEvaluator (body) uses this to find untested symbols;
the coverage scan (shared, test_coverage.yaml ``exempt_modules_without_public_symbols``)
uses it to exempt modules that have none (governor ruling 2026-10-03) and to
report modules whose test file leaves public symbols untested (2026-10-20).
Both import it from here so the two cannot diverge.

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


# ID: 5b725e7f-10be-4330-9f70-71d478d1a5b2
def tested_symbol_names(test_path: Path) -> set[str]:
    """Return symbol names covered by test_<name> functions/methods in test_path.

    Module-level test_<name> → covers top-level symbol <name>.
    TestClassName.test_<method> → covers class method ClassName.<method>.
    Raises ``SyntaxError`` when the test file cannot be parsed.
    """
    source = test_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(test_path))
    tested: set[str] = set()
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("test_"):
                tested.add(node.name[5:])
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            class_name = node.name[4:]
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if child.name.startswith("test_"):
                        tested.add(f"{class_name}.{child.name[5:]}")
    return tested


# ID: 91590677-63ee-4264-b02e-6d2a2fdcfad5
def symbol_is_tested(
    name: str, tested_keys: set[str], leaf_counts: dict[str, int]
) -> bool:
    """True when a test name in ``tested_keys`` covers symbol ``name``.

    ``tested_keys`` are normalized test names (``name_key``); ``leaf_counts``
    counts each normalized leaf name across the module's symbols.

    The generator prompt asks for test_{symbol_name}; for a method
    "Class.method" that is not an identifier, so the LLM lands it as
    test_Class_method or test_class_method. Compare a normalized form
    (lowercase, no '_' or '.'), or the remediator re-mints the same
    symbol after every landing (2026-10-02 loop).

    A method "Class.method" is also covered by a bare test_<method> when
    no other symbol in this file has that method/function name — the
    generator often drops the class, and an unrecognised landing is
    re-minted every cycle with the same function name, shadowing the
    previous copy (2026-10-03 loop: LoggingChecks.check_logger_not_presentation
    minted 8 times overnight). Ambiguous bare names (e.g. `verify` on
    several classes) are never credited.
    """
    leaf_key = name_key(name.rsplit(".", 1)[-1])
    bare_method_covered = (
        "." in name and leaf_counts.get(leaf_key) == 1 and leaf_key in tested_keys
    )
    return name_key(name) in tested_keys or bare_method_covered


# ID: d9b58ff1-f72b-4a41-802d-7abe21ff0883
def leaf_name_counts(names: list[str]) -> dict[str, int]:
    """Count each symbol name's normalized leaf (the part after the last '.')."""
    counts: dict[str, int] = {}
    for name in names:
        leaf = name_key(name.rsplit(".", 1)[-1])
        counts[leaf] = counts.get(leaf, 0) + 1
    return counts


# ID: 4d4addf5-7e1a-47cc-8b0c-7c078555c753
def has_untested_public_symbols(source_path: Path, test_path: Path) -> bool:
    """True when ``test_path`` leaves at least one public symbol untested.

    An unparseable source or test file counts as untested: the gap
    evaluator then treats every symbol as a gap, so the scan must not
    report the module as covered.
    """
    try:
        symbols = extract_public_symbols(source_path)
    except (SyntaxError, UnicodeDecodeError, OSError):
        return True
    if not symbols:
        return False
    try:
        tested_keys = {name_key(n) for n in tested_symbol_names(test_path)}
    except (SyntaxError, UnicodeDecodeError, OSError):
        return True
    leaf_counts = leaf_name_counts([sym.name for sym in symbols])
    return any(
        not symbol_is_tested(sym.name, tested_keys, leaf_counts) for sym in symbols
    )


# ID: 674c481e-5497-4349-8a73-a0bcfe09110d
def name_key(name: str) -> str:
    """Case- and separator-insensitive key: 'Svc.run' == 'Svc_run' == 'svc_run'."""
    return name.lower().replace("_", "").replace(".", "")


def _format_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args = [arg.arg for arg in node.args.args]
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    return f"{prefix} {node.name}({', '.join(args)})"
