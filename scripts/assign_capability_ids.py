#!/usr/bin/env python3
"""
Assign deterministic '# ID: <uuid>' tags to top-level public symbols.

- Only for top-level def/class (no methods).
- Skips names starting with '_' (private/dunder).
- Skips paths forbidden by your policies:
    - .intent/**
    - src/system/governance/**
    - src/core/**
- Excludes tests/**.
- Deterministic UUIDv5 based on "repo-relative-path::SymbolName".
- Adds the tag one line above the symbol definition.
- Dry-run by default; use --write to modify files.
"""

import ast
import argparse
import re
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]  # tools/ -> repo root
SRC_DIR = REPO_ROOT / "src"

FORBIDDEN_GLOBS = [
    ".intent/**",
    "src/system/governance/**",
    "src/core/**",
]
EXCLUDE_DIRS = {".git", "tests", ".venv", "venv", ".idea", ".vscode", "reports", "work"}

ID_PATTERN = re.compile(r"^\s*#\s*ID:\s*([0-9a-fA-F-]{36})\s*$")
DEF_PATTERN = re.compile(r"^(class|def)\s+([A-Za-z_][A-Za-z0-9_]*)\s*[\(:]")

# Stable namespace for capability IDs (do NOT change once chosen)
CAP_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://core.local/capability")

def is_forbidden(path: Path) -> bool:
    rp = path.as_posix()
    for glob in FORBIDDEN_GLOBS:
        if path.match(glob) or rp.startswith(glob.rstrip("/**")):
            return True
    return False

def has_id_tag(lines, start_idx) -> bool:
    """
    Look upwards a few lines from the def/class line to find '# ID: <uuid>'.
    """
    for i in range(max(0, start_idx - 3), start_idx):
        if ID_PATTERN.match(lines[i]):
            return True
    return False

def compute_id(repo_rel: str, symbol: str) -> str:
    return str(uuid.uuid5(CAP_NAMESPACE, f"{repo_rel}::{symbol}"))

def find_top_level_symbols(py_path: Path):
    """
    Return list of (name, lineno) for top-level public functions/classes.
    """
    try:
        text = py_path.read_text(encoding="utf-8")
    except Exception:
        return []

    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []

    symbols = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            name = node.name
            if not name.startswith("_"):
                symbols.append((name, node.lineno))
    return symbols

def should_skip_file(path: Path) -> bool:
    if not path.name.endswith(".py"):
        return True
    # Exclude known dirs
    for part in path.parts:
        if part in EXCLUDE_DIRS:
            return True
    # Forbidden policy globs
    if is_forbidden(path):
        return True
    return False

def process_file(py_path: Path, write: bool):
    repo_rel = py_path.relative_to(REPO_ROOT).as_posix()
    text = py_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    # Map line number -> already tagged?
    # We’ll also scan for top-level defs via regex as a guard against ast lineno drift after edits
    changes = []
    symbols = find_top_level_symbols(py_path)
    if not symbols:
        return 0, []

    # Build mapping of def line numbers for quick check
    def_lines = {lineno for _, lineno in symbols}

    # Walk through lines; when we find a top-level def/class line, check for ID
    inserted = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        if DEF_PATTERN.match(line) and (i + 1) in def_lines:
            # top-level by lineno match (lineno is 1-based)
            # if file already has an ID tag above within 3 lines, skip
            if not has_id_tag(lines, i):
                # extract symbol name
                m = DEF_PATTERN.match(line)
                symbol_name = m.group(2) if m else "UNKNOWN"
                cap_id = compute_id(repo_rel, symbol_name)
                tag_line = f"# ID: {cap_id}"
                lines.insert(i, tag_line)
                inserted += 1
                i += 1  # skip over the inserted line
                changes.append((symbol_name, cap_id, i + 1))  # approx position after insert
        i += 1

    if inserted and write:
        py_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return inserted, changes

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="Apply changes to files.")
    ap.add_argument("--limit", type=int, default=0, help="Stop after assigning this many IDs (0 = no limit).")
    args = ap.parse_args()

    total_inserted = 0
    change_log = []

    candidates = sorted(SRC_DIR.rglob("*.py"))
    for path in candidates:
        if should_skip_file(path):
            continue
        inserted, changes = process_file(path, write=args.write)
        if inserted:
            total_inserted += inserted
            change_log.extend([(path.relative_to(REPO_ROOT).as_posix(),) + c for c in changes])
            if args.limit and total_inserted >= args.limit:
                break

    mode = "WRITE" if args.write else "DRY-RUN"
    print(f"\n[{mode}] Assigned {total_inserted} capability ID tag(s).")
    if change_log:
        print("Changed symbols:")
        for file_path, sym, cap_id, line_no in change_log:
            print(f"  - {file_path}:{line_no}  {sym}  ->  # ID: {cap_id}")

if __name__ == "__main__":
    main()
