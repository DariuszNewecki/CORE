#!/usr/bin/env python3
"""Pre-commit hook: verify UUID presence on new public symbols, block duplicate IDs.

Usage (pre-commit runs this automatically):
  python hooks/check_symbol_ids.py <file1.py> [<file2.py> ...]

Checks applied to staged additions only (no retroactive enforcement on existing code):
  1. Every new public def/class in src/ must have "# ID: <uuid-v4>" on the
     immediately preceding line in the staged file.
  2. A UUID introduced in this commit must not already exist elsewhere in src/.
  3. Placeholder IDs ("# ID: xxxxxxxx-...") are rejected on the preceding line.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


_UUID_RE = re.compile(
    r"# ID: ([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
    re.IGNORECASE,
)
_PLACEHOLDER_RE = re.compile(r"# ID: [xX]{8,}-")
_PUBLIC_DEF_RE = re.compile(r"^( *)(async +)?(?:def|class) +([A-Za-z_]\w*)")


def _staged_content(file_path: str) -> list[str]:
    r = subprocess.run(
        ["git", "show", f":0:{file_path}"], capture_output=True, text=True
    )
    return r.stdout.splitlines() if r.returncode == 0 else []


def _added_linenos(file_path: str) -> set[int]:
    """Return 1-based line numbers of lines added in the staged diff."""
    r = subprocess.run(
        ["git", "diff", "--cached", "--unified=0", file_path],
        capture_output=True,
        text=True,
    )
    added: set[int] = set()
    lineno = 0
    for line in r.stdout.splitlines():
        hunk = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
        if hunk:
            lineno = int(hunk.group(1))
        elif line.startswith("+") and not line.startswith("+++"):
            added.add(lineno)
            lineno += 1
        elif not line.startswith("-"):
            lineno += 1
    return added


def _collect_existing_uuids(src: Path, exclude_files: set[str]) -> dict[str, str]:
    """Collect all UUIDs in src/ except the files being staged (they're checked separately)."""
    seen: dict[str, str] = {}
    for py in sorted(src.rglob("*.py")):
        rel = str(py.relative_to(src.parent))
        if rel in exclude_files:
            continue
        for m in _UUID_RE.finditer(py.read_text(encoding="utf-8", errors="replace")):
            uid = m.group(1).lower()
            seen.setdefault(uid, rel)
    return seen


def _check_staged_files(files: list[str]) -> list[str]:
    src_files = [f for f in files if f.startswith("src/") and f.endswith(".py")]
    if not src_files:
        return []

    errors: list[str] = []
    existing = _collect_existing_uuids(Path("src"), set(src_files))
    new_uuids: dict[str, str] = {}  # uid → "file:lineno"

    for f in src_files:
        added = _added_linenos(f)
        if not added:
            continue
        lines = _staged_content(f)

        for lineno in sorted(added):
            idx = lineno - 1
            if idx >= len(lines):
                continue

            # Check def/class lines for missing/placeholder IDs
            dm = _PUBLIC_DEF_RE.match(lines[idx])
            if dm and not dm.group(3).startswith("_"):
                name = dm.group(3)
                prev = lines[idx - 1].rstrip() if idx > 0 else ""
                if _PLACEHOLDER_RE.search(prev):
                    errors.append(
                        f"{f}:{lineno}: placeholder ID on '{name}' — use a real UUID v4"
                    )
                elif not _UUID_RE.search(prev):
                    errors.append(
                        f"{f}:{lineno}: public '{name}' missing '# ID: <uuid-v4>' on preceding line"
                    )

            # Check added UUID lines for duplicates
            um = _UUID_RE.search(lines[idx])
            if um:
                uid = um.group(1).lower()
                loc = f"{f}:{lineno}"
                if uid in new_uuids:
                    errors.append(
                        f"Duplicate UUID {uid}: added at {new_uuids[uid]} and {loc}"
                    )
                elif uid in existing:
                    errors.append(
                        f"UUID {uid} at {loc} already exists in {existing[uid]}"
                    )
                else:
                    new_uuids[uid] = loc

    return errors


def main() -> int:
    errors = _check_staged_files(sys.argv[1:])
    for e in errors:
        print(f"  {e}", file=sys.stderr)
    if errors:
        print(
            f"\ncheck_symbol_ids: {len(errors)} violation(s). See CLAUDE.md §Symbol IDs.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
