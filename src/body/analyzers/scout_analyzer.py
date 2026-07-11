# src/body/analyzers/scout_analyzer.py

"""Scout Analyzer — PARSE-phase detection of repository governance signals (ADR-146 D2).

Walks a target repository's Python files and extracts aggregate AST-based signals
for downstream rule induction. Read-only, deterministic, no side effects.

CONSTITUTIONAL:
- PARSE phase: pure read, no mutations.
- No import from mind/, will/, or direct LLM calls.
- Receives target path via execute() kwargs — no Settings dependency.
"""

from __future__ import annotations

import ast
import hashlib
import time
from pathlib import Path
from typing import Any

from body.analyzers.base_analyzer import BaseAnalyzer
from shared.component_primitive import ComponentResult
from shared.logger import getLogger


logger = getLogger(__name__)

_SKIP_DIR_PARTS: frozenset[str] = frozenset(
    {".venv", "venv", "build", "dist", "__pycache__", "node_modules", ".git"}
)


# ID: c61458b4-044b-45ae-9b39-a6dfd45392e4
class ScoutAnalyzer(BaseAnalyzer):
    """Extract aggregate governance signals from a target repository's Python source.

    Returns ComponentResult with data keys:
    - signals_text: formatted signal report string for LLM consumption
    - signals_raw: raw signal dict for structured API response
    - cache_key: 16-hex SHA-256 of signal report (used by callers for caching)
    """

    # ID: 60e30822-107d-44e2-9192-d6c9cc7306a4
    async def execute(self, repo_path: Path | str, **kwargs: Any) -> ComponentResult:
        """Walk repo_path and extract governance signals.

        Args:
            repo_path: Root path of the target repository to analyse.

        Returns:
            ComponentResult with ok=True and signals_text / signals_raw in data.
        """
        start = time.monotonic()
        target = Path(repo_path).resolve()

        if not target.is_dir():
            return ComponentResult(
                component_id=self.component_id,
                ok=False,
                data={"error": f"Not a directory: {target}"},
                phase=self.phase,
                confidence=0.0,
            )

        try:
            raw = _extract_repo_signals(target)
            text = _format_signal_report(raw)
            key = hashlib.sha256(text.encode()).hexdigest()[:16]
        except Exception as exc:
            logger.error(
                "ScoutAnalyzer: signal extraction failed: %s", exc, exc_info=True
            )
            return ComponentResult(
                component_id=self.component_id,
                ok=False,
                data={"error": str(exc)},
                phase=self.phase,
                confidence=0.0,
            )

        elapsed = time.monotonic() - start
        return ComponentResult(
            component_id=self.component_id,
            ok=True,
            data={
                "signals_text": text,
                "signals_raw": raw,
                "cache_key": key,
            },
            phase=self.phase,
            confidence=1.0,
            duration_sec=elapsed,
            metadata={
                "repo_path": str(target),
                "py_files": raw.get("total_py_files", 0),
                "files_parsed": raw.get("files_parsed", 0),
            },
        )


# ── Detection helpers (no CORE imports — pure stdlib/ast) ─────────────────────


def _should_include_file(p: Path, root: Path) -> bool:
    try:
        rel = p.relative_to(root)
    except ValueError:
        return True
    return not any(part in _SKIP_DIR_PARTS for part in rel.parts)


def _get_decorator_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Call):
        return _get_decorator_name(node.func)
    return ""


def _has_docstring(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
) -> bool:
    return (
        bool(node.body)
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    )


def _extract_ci_signals(target_root: Path) -> dict[str, Any]:
    pyproject = target_root / "pyproject.toml"
    if not pyproject.exists():
        return {}
    try:
        import tomllib

        with pyproject.open("rb") as f:
            doc = tomllib.load(f)
        tool = doc.get("tool", {})
        result: dict[str, Any] = {}
        mypy = tool.get("mypy", {})
        if mypy:
            result["mypy_configured"] = True
            if mypy.get("strict"):
                result["mypy_strict"] = True
        ruff = tool.get("ruff", {})
        ruff_select = ruff.get("lint", {}).get("select") or ruff.get("select")
        if ruff_select:
            result["ruff_select"] = list(ruff_select)[:12]
        return result
    except Exception:
        return {}


# ID: b01fa213-5eea-45ac-8a2e-7b90ec258083
def _extract_repo_signals(target_root: Path) -> dict[str, Any]:
    """Walk the full repository and extract aggregate AST-based governance signals."""
    all_py = sorted(
        p for p in target_root.rglob("*.py") if _should_include_file(p, target_root)
    )

    files_parsed = 0
    files_failed = 0
    test_file_count = 0
    public_defs = 0
    public_defs_docstring = 0
    public_defs_annotated = 0
    public_classes = 0
    public_classes_docstring = 0
    future_annotations_files = 0
    type_checking_files = 0
    bare_except_count = 0
    typed_except_pass_count = 0
    print_call_count = 0
    abstract_methods = 0
    import_alias_counts: dict[str, int] = {}
    decorator_counts: dict[str, int] = {}

    for py_file in all_py:
        try:
            source = py_file.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(py_file))
        except Exception:
            files_failed += 1
            continue
        files_parsed += 1

        name = py_file.name
        if name.startswith("test_") or name.endswith("_test.py"):
            test_file_count += 1

        file_has_future = False
        file_has_type_checking = False

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == "__future__" and any(
                    a.name == "annotations" for a in node.names
                ):
                    file_has_future = True

            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.asname:
                        key = f"import {alias.name} as {alias.asname}"
                        import_alias_counts[key] = import_alias_counts.get(key, 0) + 1

            elif isinstance(node, ast.If):
                test = node.test
                if (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
                    isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
                ):
                    file_has_type_checking = True

            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                if not node.name.startswith("_"):
                    public_defs += 1
                    if node.returns is not None:
                        public_defs_annotated += 1
                    if _has_docstring(node):
                        public_defs_docstring += 1
                    for dec in node.decorator_list:
                        dec_name = _get_decorator_name(dec)
                        if dec_name:
                            decorator_counts[dec_name] = (
                                decorator_counts.get(dec_name, 0) + 1
                            )
                        if dec_name == "abstractmethod":
                            abstract_methods += 1

            elif isinstance(node, ast.ClassDef):
                if not node.name.startswith("_"):
                    public_classes += 1
                    if _has_docstring(node):
                        public_classes_docstring += 1

            elif isinstance(node, ast.ExceptHandler):
                if node.type is None:
                    bare_except_count += 1
                elif len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                    typed_except_pass_count += 1

            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "print":
                    print_call_count += 1

        if file_has_future:
            future_annotations_files += 1
        if file_has_type_checking:
            type_checking_files += 1

    return {
        "total_py_files": len(all_py),
        "files_parsed": files_parsed,
        "files_failed": files_failed,
        "test_files": test_file_count,
        "has_src_layout": (target_root / "src").is_dir(),
        "public_defs": public_defs,
        "public_defs_docstring": public_defs_docstring,
        "public_defs_annotated": public_defs_annotated,
        "public_classes": public_classes,
        "public_classes_docstring": public_classes_docstring,
        "future_annotations_files": future_annotations_files,
        "type_checking_files": type_checking_files,
        "bare_except_count": bare_except_count,
        "typed_except_pass_count": typed_except_pass_count,
        "print_call_count": print_call_count,
        "abstract_methods": abstract_methods,
        "py_typed": (target_root / "py.typed").exists()
        or bool(list(target_root.glob("src/*/py.typed"))),
        "top_aliases": sorted(import_alias_counts.items(), key=lambda x: -x[1])[:8],
        "top_decorators": sorted(decorator_counts.items(), key=lambda x: -x[1])[:8],
        "ci_signals": _extract_ci_signals(target_root),
    }


# ID: c172cb5b-890a-484d-a671-687bc710845a
def _format_signal_report(signals: dict[str, Any]) -> str:
    """Format aggregate repo signals as a structured text report for the LLM."""
    total = signals["total_py_files"]
    parsed = signals["files_parsed"]
    failed = signals["files_failed"]
    test_files = signals["test_files"]
    pub_defs = signals["public_defs"]
    annotated = signals["public_defs_annotated"]
    defs_doc = signals["public_defs_docstring"]
    pub_cls = signals["public_classes"]
    cls_doc = signals["public_classes_docstring"]
    future_ann = signals["future_annotations_files"]
    tc_files = signals["type_checking_files"]
    bare_exc = signals["bare_except_count"]
    typed_pass = signals["typed_except_pass_count"]
    prints = signals["print_call_count"]
    abstract = signals["abstract_methods"]
    py_typed = signals["py_typed"]

    # ID: 94e751ba-1f2f-45c2-b7ef-7d4dcafb5073
    def pct(n: int, of: int) -> str:
        return f"{int(n / of * 100)}%" if of else "n/a"

    parts: list[str] = [
        f"Python files: {total} total  {parsed} parsed  {failed} failed  {test_files} test files",
        f"Project layout: {'src/' if signals.get('has_src_layout') else 'flat'}  py.typed: {'yes' if py_typed else 'no'}",
        "",
        "Public symbols (full-repo, non-underscore functions and classes):",
        f"  functions/methods : {pub_defs}",
        f"    with return annotation : {annotated}  ({pct(annotated, pub_defs)})",
        f"    with docstring         : {defs_doc}  ({pct(defs_doc, pub_defs)})",
        f"  classes           : {pub_cls}",
        f"    with docstring         : {cls_doc}  ({pct(cls_doc, pub_cls)})",
        "",
        "Pattern counts (full-repo):",
        f"  from __future__ import annotations : {future_ann} files  ({pct(future_ann, parsed)})",
        f"  if TYPE_CHECKING guard             : {tc_files} files",
        f"  bare except (untyped)              : {bare_exc}",
        f"  typed except + pass (silenced)     : {typed_pass}",
        f"  print() calls                      : {prints}",
        f"  @abstractmethod usage              : {abstract}",
    ]

    top_aliases = signals.get("top_aliases", [])
    if top_aliases:
        parts += ["", "Import aliasing patterns (top by file count):"]
        for alias, count in top_aliases:
            parts.append(f"  {alias}  →  {count} files")

    top_dec = signals.get("top_decorators", [])
    if top_dec:
        parts += ["", "Decorator inventory (top by usage count):"]
        for dec, count in top_dec:
            parts.append(f"  @{dec}  →  {count} uses")

    ci = signals.get("ci_signals", {})
    if ci:
        parts += ["", "CI / tooling:"]
        if "mypy_configured" in ci:
            strict = ci.get("mypy_strict", False)
            parts.append(
                f"  mypy: configured  {'strict=true' if strict else 'non-strict'}"
            )
        ruff_select = ci.get("ruff_select")
        if ruff_select:
            parts.append(f"  ruff select: {ruff_select}")

    return "\n".join(parts)
