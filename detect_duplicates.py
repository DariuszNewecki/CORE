#!/usr/bin/env python3
"""
detect_duplicates.py

Repo-agnostic duplicate detection for Python code using:
- exact text hash
- normalized text hash (strip comments/whitespace/docstrings)
- canonical AST hash (rename locals, normalize literals, drop annotations)

Outputs:
- duplicates.json
- duplicates.md
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import io
import json
import tokenize
from collections import defaultdict
from pathlib import Path
from typing import Any


# -----------------------------
# Data model
# -----------------------------
@dataclasses.dataclass(frozen=True)
class Symbol:
    file: str
    qualname: str
    kind: str  # function | method
    start: int
    end: int
    nlines: int
    raw_hash: str
    norm_text_hash: str
    canon_ast_hash: str
    token_count: int


# -----------------------------
# Utilities
# -----------------------------
def sha256_hex(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8", errors="ignore")).hexdigest()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def is_python_file(path: Path) -> bool:
    return path.suffix == ".py" and path.is_file()


def safe_end_lineno(node: ast.AST, fallback: int) -> int:
    end = getattr(node, "end_lineno", None)
    if isinstance(end, int):
        return end
    return fallback


def qualname(stack: list[str], name: str) -> str:
    if stack:
        return ".".join(stack + [name])
    return name


def strip_docstring_from_block(stmts: list[ast.stmt]) -> list[ast.stmt]:
    if not stmts:
        return stmts
    first = stmts[0]
    if isinstance(first, ast.Expr) and isinstance(
        getattr(first, "value", None), ast.Constant
    ):
        if isinstance(first.value.value, str):
            return stmts[1:]
    return stmts


# -----------------------------
# Normalized text (token-based)
# -----------------------------
def normalized_text(source: str) -> tuple[str, int]:
    """
    Produce a normalized token stream:
    - remove comments, NL/NEWLINE/INDENT/DEDENT
    - keep NAME/OP/STRING/NUMBER etc
    - collapse whitespace
    Return (normalized_text, token_count).
    """
    out: list[str] = []
    tok_count = 0
    try:
        g = tokenize.generate_tokens(io.StringIO(source).readline)
        for tok in g:
            ttype = tok.type
            tstr = tok.string

            if ttype in (
                tokenize.COMMENT,
                tokenize.NL,
                tokenize.NEWLINE,
                tokenize.INDENT,
                tokenize.DEDENT,
                tokenize.ENCODING,
            ):
                continue
            if ttype == tokenize.ENDMARKER:
                break

            # Keep significant tokens; normalize whitespace by joining with single spaces
            out.append(tstr)
            tok_count += 1
    except tokenize.TokenError:
        # Fallback: crude whitespace normalization
        collapsed = " ".join(source.split())
        return collapsed, len(collapsed.split())

    return " ".join(out), tok_count


# -----------------------------
# Canonical AST normalizer
# -----------------------------
class Canonicalizer(ast.NodeTransformer):
    """
    Canonicalize a function/method AST:
    - remove type annotations / return annotations
    - normalize constants
    - rename local identifiers deterministically
    - drop docstring nodes
    """

    def __init__(self) -> None:
        super().__init__()
        self._name_map: dict[str, str] = {}
        self._name_counter = 0

    def _canon_name(self, original: str) -> str:
        # Preserve common semantic names that matter less? (You can tweak)
        # Here we canonicalize all locals/args.
        if original not in self._name_map:
            self._name_counter += 1
            self._name_map[original] = f"VAR_{self._name_counter}"
        return self._name_map[original]

    # --- Core transforms ---
    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        node.returns = None
        node.decorator_list = []  # optional: ignore decorators to catch more duplicates
        node.args = self.visit(node.args)
        node.body = [self.visit(s) for s in strip_docstring_from_block(node.body)]
        node.type_comment = None
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        node.returns = None
        node.decorator_list = []
        node.args = self.visit(node.args)
        node.body = [self.visit(s) for s in strip_docstring_from_block(node.body)]
        node.type_comment = None
        return node

    def visit_arguments(self, node: ast.arguments) -> Any:
        # Drop annotations
        for arg in list(node.posonlyargs) + list(node.args) + list(node.kwonlyargs):
            arg.annotation = None
        if node.vararg:
            node.vararg.annotation = None
        if node.kwarg:
            node.kwarg.annotation = None
        node.defaults = [self.visit(d) for d in node.defaults]
        node.kw_defaults = [
            self.visit(d) if d is not None else None for d in node.kw_defaults
        ]
        return node

    def visit_AnnAssign(self, node: ast.AnnAssign) -> Any:
        # Convert annotated assignment to plain assign
        target = self.visit(node.target)
        value = (
            self.visit(node.value)
            if node.value is not None
            else ast.Constant(value=None)
        )
        return ast.Assign(targets=[target], value=value, type_comment=None)

    def visit_arg(self, node: ast.arg) -> Any:
        # Rename args
        node.arg = self._canon_name(node.arg)
        node.annotation = None
        return node

    def visit_Name(self, node: ast.Name) -> Any:
        # Rename variable identifiers (locals & params)
        node.id = self._canon_name(node.id)
        return node

    def visit_Attribute(self, node: ast.Attribute) -> Any:
        # Keep attribute names (often semantically relevant), but canonicalize the value object.
        node.value = self.visit(node.value)
        return node

    def visit_Constant(self, node: ast.Constant) -> Any:
        v = node.value
        if isinstance(v, str):
            return ast.Constant(value="STR")
        if isinstance(v, (int, float, complex)):
            return ast.Constant(value=0)
        if isinstance(v, bool):
            return ast.Constant(value=False)
        if v is None:
            return ast.Constant(value=None)
        # Fallback for bytes/other constants
        return ast.Constant(value="CONST")

    def visit_JoinedStr(self, node: ast.JoinedStr) -> Any:
        # f-strings -> STR
        return ast.Constant(value="STR")

    def visit_Call(self, node: ast.Call) -> Any:
        # Keep function/attribute name structure, canonicalize args/keywords
        node.func = self.visit(node.func)
        node.args = [self.visit(a) for a in node.args]
        node.keywords = [self.visit(k) for k in node.keywords]
        return node

    def visit_keyword(self, node: ast.keyword) -> Any:
        # Normalize kw names? Keep them (often matters), but canonicalize values.
        node.value = self.visit(node.value)
        return node


def canonical_ast_hash(func_node: ast.AST) -> str:
    """
    Return hash of canonical AST dump of a single function/method node.
    """
    node = ast.fix_missing_locations(func_node)
    canon = Canonicalizer().visit(ast.copy_location(func_node, func_node))
    ast.fix_missing_locations(canon)
    dumped = ast.dump(canon, annotate_fields=True, include_attributes=False)
    return sha256_hex(dumped)


# -----------------------------
# AST extraction
# -----------------------------
class Extractor(ast.NodeVisitor):
    def __init__(self, file: Path, source: str) -> None:
        self.file = file
        self.source = source
        self.lines = source.splitlines()
        self.stack: list[str] = []
        self.symbols: list[tuple[ast.AST, str, str]] = []  # (node, qualname, kind)

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        qn = qualname(self.stack, node.name)
        kind = "method" if self.stack else "function"
        self.symbols.append((node, qn, kind))
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        qn = qualname(self.stack, node.name)
        kind = "method" if self.stack else "function"
        self.symbols.append((node, qn, kind))
        self.generic_visit(node)


def slice_source(lines: list[str], start: int, end: int) -> str:
    # start/end are 1-based inclusive
    start_i = max(start - 1, 0)
    end_i = min(end, len(lines))
    return "\n".join(lines[start_i:end_i]) + "\n"


# -----------------------------
# Duplicate clustering
# -----------------------------
def cluster_by_key(symbols: list[Symbol], key: str) -> dict[str, list[Symbol]]:
    buckets: dict[str, list[Symbol]] = defaultdict(list)
    for s in symbols:
        buckets[getattr(s, key)].append(s)
    # keep only duplicates
    return {k: v for k, v in buckets.items() if len(v) > 1}


def rank_group(group: list[Symbol]) -> tuple[int, int]:
    # rank: bigger groups and bigger code first
    size = len(group)
    tokens = sum(s.token_count for s in group)
    return (size, tokens)


def to_rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


# -----------------------------
# Main
# -----------------------------
def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--root", default="/opt/dev/CORE/src", help="Root directory to scan"
    )
    ap.add_argument(
        "--min-tokens",
        type=int,
        default=25,
        help="Skip symbols smaller than this token count",
    )
    ap.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Exclude path fragments (repeatable)",
    )
    ap.add_argument(
        "--include-tests", action="store_true", help="Include tests (default: excluded)"
    )
    ap.add_argument("--outdir", default=".", help="Output directory")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    outdir = Path(args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    excludes = set(args.exclude)
    if not args.include_tests:
        excludes.update({"tests", "test_", "/tests/"})

    all_symbols: list[Symbol] = []

    for path in root.rglob("*.py"):
        if not is_python_file(path):
            continue
        rel = str(path)
        if any(x in rel for x in excludes):
            continue

        try:
            src = read_text(path)
            tree = ast.parse(src)
        except SyntaxError:
            continue

        ex = Extractor(path, src)
        ex.visit(tree)

        for node, qn, kind in ex.symbols:
            start = getattr(node, "lineno", None)
            if not isinstance(start, int):
                continue
            end = safe_end_lineno(node, start)
            chunk = slice_source(ex.lines, start, end)

            norm_text, tok_count = normalized_text(chunk)
            if tok_count < args.min_tokens:
                continue

            raw_hash = sha256_hex(chunk)
            norm_hash = sha256_hex(norm_text)

            # canonical AST hash
            try:
                canon_hash = canonical_ast_hash(node)
            except Exception:
                canon_hash = "ERROR"

            all_symbols.append(
                Symbol(
                    file=to_rel(path, root),
                    qualname=qn,
                    kind=kind,
                    start=start,
                    end=end,
                    nlines=(end - start + 1),
                    raw_hash=raw_hash,
                    norm_text_hash=norm_hash,
                    canon_ast_hash=canon_hash,
                    token_count=tok_count,
                )
            )

    # Clusters
    clusters = {
        "exact_text": cluster_by_key(all_symbols, "raw_hash"),
        "normalized_text": cluster_by_key(all_symbols, "norm_text_hash"),
        "canonical_ast": {
            k: v
            for k, v in cluster_by_key(all_symbols, "canon_ast_hash").items()
            if k != "ERROR"
        },
    }

    # Build JSON report
    report: dict[str, Any] = {
        "root": str(root),
        "stats": {
            "symbols_total": len(all_symbols),
            "duplicates_exact_text_groups": len(clusters["exact_text"]),
            "duplicates_normalized_text_groups": len(clusters["normalized_text"]),
            "duplicates_canonical_ast_groups": len(clusters["canonical_ast"]),
        },
        "groups": [],
    }

    def emit_groups(kind: str, bucket: dict[str, list[Symbol]]) -> None:
        items = sorted(bucket.items(), key=lambda kv: rank_group(kv[1]), reverse=True)
        for gid, syms in items:
            group = sorted(syms, key=lambda s: (s.file, s.start))
            report["groups"].append(
                {
                    "kind": kind,
                    "group_key": gid,
                    "count": len(group),
                    "tokens_total": sum(s.token_count for s in group),
                    "symbols": [
                        {
                            "file": s.file,
                            "qualname": s.qualname,
                            "kind": s.kind,
                            "lines": [s.start, s.end],
                            "tokens": s.token_count,
                        }
                        for s in group
                    ],
                }
            )

    emit_groups("exact_text", clusters["exact_text"])
    emit_groups("normalized_text", clusters["normalized_text"])
    emit_groups("canonical_ast", clusters["canonical_ast"])

    json_path = outdir / "duplicates.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    # Build Markdown triage
    md_lines: list[str] = []
    md_lines.append("# Duplicate Report\n")
    md_lines.append(f"- Root: `{root}`")
    md_lines.append(f"- Symbols scanned: **{report['stats']['symbols_total']}**")
    md_lines.append(
        f"- Exact text duplicate groups: **{report['stats']['duplicates_exact_text_groups']}**"
    )
    md_lines.append(
        f"- Normalized text duplicate groups: **{report['stats']['duplicates_normalized_text_groups']}**"
    )
    md_lines.append(
        f"- Canonical AST duplicate groups: **{report['stats']['duplicates_canonical_ast_groups']}**\n"
    )

    # Show top groups
    groups_sorted = sorted(
        report["groups"], key=lambda g: (g["count"], g["tokens_total"]), reverse=True
    )
    top = groups_sorted[:50]

    md_lines.append("## Top duplicate groups (by size × tokens)\n")
    for i, g in enumerate(top, 1):
        md_lines.append(
            f"### {i}. {g['kind']} — {g['count']} symbols — {g['tokens_total']} tokens\n"
        )
        for s in g["symbols"]:
            md_lines.append(
                f"- `{s['file']}:{s['lines'][0]}-{s['lines'][1]}` — `{s['qualname']}` ({s['kind']}, {s['tokens']} tokens)"
            )
        md_lines.append("")

    md_path = outdir / "duplicates.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    print(f"Wrote: {json_path}")
    print(f"Wrote: {md_path}")
    print("Done.")


if __name__ == "__main__":
    main()
