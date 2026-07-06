# src/body/introspection/id_anchor_scanner.py
"""
Pure filesystem scanner — extracts # ID: anchored public symbols from src/.

ADR-143 D2: source-side half of the symbols-drift check.
No DB access, no LLM, no side effects.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


_UUID_RE = re.compile(
    r"^# ID: ([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$",
    re.IGNORECASE,
)
_SYMBOL_RE = re.compile(r"^(?:async )?(?:def|class) ([A-Za-z_]\w*)")

_SAMPLE_CAP = 50


@dataclass(frozen=True)
# ID: 3f8a1c2d-4e5f-6a7b-8c9d-0e1f2a3b4c5d
class AnchoredSymbol:
    file_path: str  # repo-relative, e.g. "src/body/foo.py"
    symbol_path: str  # e.g. "src/body/foo.py::my_func"
    anchor_uuid: str


@dataclass(frozen=True)
# ID: 4a9b2d3e-5f6a-7b8c-9d0e-1f2a3b4c5d6e
class ScanResult:
    anchored: frozenset[AnchoredSymbol]
    anchor_missing: frozenset[str]  # symbol_paths of public def/class without # ID:


# ID: 5b0c3e4f-6a7b-8c9d-0e1f-2a3b4c5d6e7f
def scan(repo_root: Path) -> ScanResult:
    """Walk src/**/*.py and produce the source-side symbol inventory.

    For each public def/class (name not starting with _):
    - If the immediately preceding non-empty line is a # ID: anchor → anchored
    - Otherwise → anchor_missing

    The symbol_path format mirrors core.symbols: "{rel_path}::{bare_name}".
    Private symbols (_name) are exempt and not included in either set.
    """
    anchored: list[AnchoredSymbol] = []
    missing: list[str] = []

    src_root = repo_root / "src"
    for py_file in sorted(src_root.rglob("*.py")):
        rel = py_file.relative_to(repo_root).as_posix()
        try:
            raw = py_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines = raw.splitlines()

        for i, raw_line in enumerate(lines):
            stripped = raw_line.strip()
            sym_m = _SYMBOL_RE.match(stripped)
            if not sym_m:
                continue
            name = sym_m.group(1)
            if name.startswith("_"):
                continue

            symbol_path = f"{rel}::{name}"

            # Search backwards for the immediately preceding non-empty line.
            # Scan up to 4 lines back to skip blank lines between # ID: and def/class.
            uuid_found: str | None = None
            for k in range(i - 1, max(i - 5, -1), -1):
                prev = lines[k].strip()
                if not prev:
                    continue
                uuid_m = _UUID_RE.match(prev)
                if uuid_m:
                    uuid_found = uuid_m.group(1).lower()
                break

            if uuid_found:
                anchored.append(
                    AnchoredSymbol(
                        file_path=rel,
                        symbol_path=symbol_path,
                        anchor_uuid=uuid_found,
                    )
                )
            else:
                missing.append(symbol_path)

    return ScanResult(
        anchored=frozenset(anchored),
        anchor_missing=frozenset(missing),
    )
