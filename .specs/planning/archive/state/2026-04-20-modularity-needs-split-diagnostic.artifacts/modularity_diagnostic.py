"""
Per-finding diagnostic for modularity.needs_split (ADR-006 candidate
reconnaissance, 2026-04-20).

Reads /tmp/needs_split_findings.json, computes 6 values per flagged
file by invoking ModularityChecker's real methods, and writes
/tmp/modularity_per_file.json.

Also computes the counterfactual: every src/**.py > 400 lines gets
_detect_responsibilities applied to it; we record who would be flagged
under "responsibilities >= 3" and cross-check against current
needs_split flags.

Read-only. No src/ or .intent/ writes.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path


REPO_ROOT = Path("/opt/dev/CORE")
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mind.logic.engines.ast_gate.checks.modularity_checks import (
    ModularityChecker,
)


_INTERNAL_PREFIXES = (
    "body",
    "mind",
    "will",
    "shared",
    "cli",
    "core",
    "infra",
    "tests",
)


def classify_imports(imports: list[str]) -> tuple[list[str], list[str]]:
    """Return (internal, external) split on the top-level module name."""
    internal: list[str] = []
    external: list[str] = []
    for imp in imports:
        top = imp.split(".", 1)[0]
        if top in _INTERNAL_PREFIXES:
            internal.append(imp)
        else:
            external.append(imp)
    return internal, external


def dominant_class_line_count(tree: ast.AST) -> tuple[int, int | None]:
    """
    Return (class_count, dominant_class_lines) where dominant_class_lines
    is the line count of the largest top-level class if that class
    accounts for >70% of all class-owned lines in the file, else None.
    class_count is the number of top-level ast.ClassDef nodes.
    """
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    if not classes:
        return 0, None

    sizes: list[int] = []
    for cls in classes:
        start = cls.lineno
        end = getattr(cls, "end_lineno", start) or start
        sizes.append(end - start + 1)

    total = sum(sizes)
    largest = max(sizes)
    if total > 0 and largest / total > 0.70:
        return len(classes), largest
    return len(classes), None


def analyze_file(checker: ModularityChecker, rel_path: str) -> dict:
    abs_path = REPO_ROOT / rel_path
    content = abs_path.read_text(encoding="utf-8")
    tree = ast.parse(content)

    imports = checker._extract_imports(tree)
    internal, external = classify_imports(imports)
    concerns = checker._identify_concerns(imports)
    responsibilities = checker._detect_responsibilities(content)
    class_count, dominant_lines = dominant_class_line_count(tree)

    return {
        "file": rel_path,
        "loc": len(content.splitlines()),
        "imports_internal": internal,
        "imports_external": external,
        "concerns": concerns,
        "responsibilities": responsibilities,
        "class_count": class_count,
        "dominant_class_lines": dominant_lines,
    }


def classify(record: dict) -> str:
    """Mutually exclusive categorisation, first match wins, in spec order."""
    concerns = len(record["concerns"])
    resp = len(record["responsibilities"])
    ext = len(record["imports_external"])
    intl = len(record["imports_internal"])
    dominant = record["dominant_class_lines"] is not None

    if concerns <= 2 and resp >= 3:
        return "CLASSIFIER-BLIND"
    if concerns <= 2 and resp <= 2 and intl > 2 * ext:
        return "INTERNAL-MODULE-NO-SIGNAL"
    if dominant:
        return "DOMINANT-CLASS"
    if (concerns >= 3 or resp >= 3) and not dominant:
        return "GENUINE-CANDIDATE"
    return "UNCATEGORIZED"


def load_findings() -> list[str]:
    findings = json.loads(Path("/tmp/needs_split_findings.json").read_text())
    return [f["file_path"] for f in findings]


def scan_all_src_over_limit(checker: ModularityChecker) -> list[dict]:
    """
    Counterfactual: every src/**/*.py over 400 LOC (ignoring __init__.py)
    gets _detect_responsibilities applied. Used to find files that
    would be flagged if the classifier were replaced and are currently
    not flagged.
    """
    results: list[dict] = []
    for path in SRC.rglob("*.py"):
        if path.name == "__init__.py":
            continue
        try:
            content = path.read_text(encoding="utf-8")
            loc = len(content.splitlines())
            if loc <= 400:
                continue
            tree = ast.parse(content)
            imports = checker._extract_imports(tree)
            concerns = checker._identify_concerns(imports)
            resps = checker._detect_responsibilities(content)
            results.append(
                {
                    "file": str(path.relative_to(REPO_ROOT)),
                    "loc": loc,
                    "concerns": concerns,
                    "responsibilities": resps,
                    "concern_count": len(concerns),
                    "responsibility_count": len(resps),
                }
            )
        except SyntaxError:
            continue
    return results


def main() -> int:
    checker = ModularityChecker()
    files = load_findings()

    per_file: list[dict] = []
    for rel in files:
        rec = analyze_file(checker, rel)
        rec["category"] = classify(rec)
        per_file.append(rec)

    per_file.sort(key=lambda r: (r["category"], r["file"]))

    Path("/tmp/modularity_per_file.json").write_text(
        json.dumps(per_file, indent=2) + "\n"
    )

    # Counterfactual scan — also written alongside.
    all_over = scan_all_src_over_limit(checker)
    Path("/tmp/modularity_counterfactual.json").write_text(
        json.dumps(all_over, indent=2) + "\n"
    )

    # Summary to stdout.
    by_cat: dict[str, int] = {}
    for rec in per_file:
        by_cat[rec["category"]] = by_cat.get(rec["category"], 0) + 1

    print(f"Total flagged: {len(per_file)}")
    for cat, n in sorted(by_cat.items(), key=lambda kv: -kv[1]):
        pct = 100.0 * n / len(per_file) if per_file else 0.0
        print(f"  {cat:30s} {n:3d}  ({pct:5.1f}%)")

    # Counterfactual numbers
    currently_flagged = {r["file"] for r in per_file}
    would_drop = [r for r in per_file if len(r["responsibilities"]) < 3]
    would_remain = [r for r in per_file if len(r["responsibilities"]) >= 3]
    would_flag_under_cf = [
        r
        for r in all_over
        if r["responsibility_count"] >= 3 and r["file"] not in currently_flagged
    ]
    print()
    print("Counterfactual (responsibilities >= 3):")
    print(f"  currently flagged, would REMAIN: {len(would_remain)}")
    print(f"  currently flagged, would DROP  : {len(would_drop)}")
    print(f"  not currently flagged, would be FLAGGED: {len(would_flag_under_cf)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
