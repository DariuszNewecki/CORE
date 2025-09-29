#!/usr/bin/env python3
# scripts/concat_project.sh
"""
Bundle the CORE project's essence for AI review.

Honors Poetry's [[tool.poetry.packages]] with `from` + `include`
(e.g., from="src", include="cli" -> "src/cli"), excludes generated
and binary files, and falls back to BODY (default: "src") if needed.
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import sys
from pathlib import Path

# Use tomllib for Python 3.11+, fall back to tomli for older versions
if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]

# --- Configuration ---
OUTPUT_FILE = "project_context.txt"
ROOT_MARKER = "pyproject.toml"

EXCLUDE_PATTERNS = [
    # dirs
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "logs",
    "sandbox",
    "pending_writes",
    "demo",
    "work",
    "dist",
    "build",
    ".intent/keys",
    # files
    ".env",
    "poetry.lock",
    # binary/globs
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.webp",
    "*.ico",
    "*.svg",
    "*.pdf",
    "*.pyc",
    "*.so",
    "*.zip",
    "*.gz",
    "*.tar",
    "*.xz",
    "*.DS_Store",
    "Thumbs.db",
]
# --- End Configuration ---


def is_excluded(path: Path, root: Path, exclude_patterns: list[str]) -> bool:
    """Return True if path should be excluded (supports dir prefixes and globs)."""
    rel = path.relative_to(root).as_posix()

    for pat in exclude_patterns:
        # Exact match
        if rel == pat or rel.rstrip("/") == pat.rstrip("/"):
            return True
        # Directory prefix (e.g., "logs/" excludes "logs/x/y")
        if rel.startswith(pat.rstrip("/") + "/"):
            return True
        # Glob pattern
        if fnmatch.fnmatch(rel, pat):
            return True
    return False


def is_likely_binary(path: Path) -> bool:
    """Heuristic: treat files containing a null byte in the first 4KB as binary."""
    try:
        with path.open("rb") as f:
            chunk = f.read(4096)
            return b"\x00" in chunk
    except Exception:
        # If we can't read it safely, skip it
        return True


def load_pyproject(root: Path) -> dict:
    py = root / ROOT_MARKER
    return tomllib.loads(py.read_text("utf-8"))


def get_include_dirs_from_pyproject(root: Path) -> list[str]:
    """
    Read pyproject.toml and honor packages entries:
      [[tool.poetry.packages]]
      from = "src"
      include = "cli"
    -> "src/cli"
    """
    cfg = load_pyproject(root)
    packages = cfg.get("tool", {}).get("poetry", {}).get("packages", [])
    resolved: set[str] = set()

    for pkg in packages:
        inc = pkg.get("include")
        frm = pkg.get("from")
        if not inc:
            continue
        p = Path(frm).joinpath(inc) if frm else Path(inc)
        resolved.add(p.as_posix())

    # Always include key non-package dirs we want bundled
    extras = {".intent", "tests", "scripts", "sql"}
    resolved |= extras

    # Fallback: if nothing resolved or none exist, include BODY (default: src)
    body = os.getenv("BODY", "src")
    if not resolved:
        resolved.add(body)
    else:
        if not any((root / d).exists() for d in resolved):
            resolved.add(body)

    # Soft warning on nonexistent include dirs
    missing = sorted(d for d in resolved if not (root / d).exists())
    if missing:
        print(f"   -> [warn] Missing include dirs (ignored): {missing}")

    return sorted(resolved)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate Project Context Bundle for AI review."
    )
    parser.add_argument(
        "--output", default=OUTPUT_FILE, help="Path for the output bundle file."
    )
    args = parser.parse_args()
    output_path = Path(args.output).resolve()

    root_path = Path.cwd()
    if not (root_path / ROOT_MARKER).exists():
        print("❌ Error: Run this from the CORE project root (pyproject.toml not found).")
        return 1

    print("🚀 Generating Project Context Bundle for AI review...")
    include_dirs = get_include_dirs_from_pyproject(root_path)
    print(f"   -> Including source directories from pyproject.toml: {include_dirs}")
    existing = [d for d in include_dirs if (root_path / d).exists()]
    print(f"   -> Resolved + existing: {existing}")

    include_root_files = [
        "pyproject.toml",
        "README.md",
        "CONTRIBUTING.md",
        "LICENSE",
        "Makefile",
        ".gitignore",
        "assesment.prompt",
        "docker-compose.yml",
    ]

    # prevent bundling the bundle
    final_exclude_patterns = EXCLUDE_PATTERNS + [
        output_path.relative_to(root_path).as_posix()
    ]

    # Gather candidate files
    files_to_bundle: list[Path] = []
    for d in include_dirs:
        p = root_path / d
        if p.is_dir():
            files_to_bundle.extend(p.rglob("*"))

    for name in include_root_files:
        p = root_path / name
        if p.is_file():
            files_to_bundle.append(p)

    # Unique & sorted
    unique_files = sorted(set(f for f in files_to_bundle if f.is_file()))

    # Write bundle
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output_path.open("w", encoding="utf-8") as out:
        out.write("--- START OF FILE project_context.txt ---\n\n")
        out.write("--- START OF PROJECT CONTEXT BUNDLE ---\n\n")

        for f in unique_files:
            if is_excluded(f, root_path, final_exclude_patterns):
                continue
            if is_likely_binary(f):
                continue

            rel = f.relative_to(root_path)
            out.write(f"--- START OF FILE ./{rel.as_posix()} ---\n")
            try:
                content = f.read_text("utf-8")
                out.write(content if content else "[EMPTY FILE]")
                count += 1
            except Exception as e:
                out.write(f"[ERROR READING FILE: {e}]")
            out.write(f"\n--- END OF FILE ./{rel.as_posix()} ---\n\n")

        out.write("--- END OF PROJECT CONTEXT BUNDLE ---\n")

    print(f"\n✅ Done. Concatenated {count} files into {output_path}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
