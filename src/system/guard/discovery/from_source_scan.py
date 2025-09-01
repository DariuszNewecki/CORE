# src/system/guard/discovery/from_source_scan.py
"""
Intent: Provides a fallback capability discovery method by scanning source
files for '# CAPABILITY:' tags.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterable, List

from system.guard.models import CapabilityMeta

_CAPABILITY_RE = re.compile("^\\s*#\\s*CAPABILITY:\\s*([A-Za-z0-9_.\\-:/]+)(.*)$")
_INLINE_KV_RE = re.compile("\\[\\s*([^\\]]+)\\s*\\]")
_KV_PAIR_RE = re.compile("([A-Za-z0-9_.\\-:/]+)\\s*=\\s*([^\\s,;]+)")


# CAPABILITY: system.guard.parse_inline_meta
def _parse_inline_meta(trailing: str) -> Dict[str, str]:
    """Parse inline [key=value] metadata from trailing text."""
    m = _INLINE_KV_RE.search(trailing or "")
    if not m:
        return {}
    return {k: v for k, v in _KV_PAIR_RE.findall(m.group(1))}


# CAPABILITY: system.files.discover
def _iter_source_files(
    root: Path, include_globs: List[str], exclude_globs: List[str]
) -> Iterable[Path]:
    """Yields repository files to be scanned."""

    def wanted(p: Path) -> bool:
        """Return True if the path matches include_globs (if any) or has a .py suffix, and does not match exclude_globs."""
        if any((p.match(g) for g in exclude_globs)):
            return False
        if include_globs:
            return any((p.match(g) for g in include_globs))
        return p.suffix in {".py"}

    for p in root.rglob("*"):
        if p.is_file() and wanted(p):
            yield p


# CAPABILITY: system.capability.discovery
def collect_from_source_scan(
    root: Path, include_globs: List[str], exclude_globs: List[str]
) -> Dict[str, CapabilityMeta]:
    """Scans for '# CAPABILITY:' tags with optional inline metadata."""
    caps: Dict[str, CapabilityMeta] = {}
    for file in _iter_source_files(root, include_globs, exclude_globs):
        try:
            for line in file.read_text(encoding="utf-8", errors="ignore").splitlines():
                m = _CAPABILITY_RE.match(line)
                if not m:
                    continue
                cap = m.group(1).strip()
                kv = _parse_inline_meta(m.group(2) or "")
                caps[cap] = CapabilityMeta(
                    capability=cap, domain=kv.get("domain"), owner=kv.get("owner")
                )
        except Exception:
            continue
    return caps
