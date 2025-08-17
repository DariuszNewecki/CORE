# src/system/guard/discovery/from_source_scan.py
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from system.guard.models import CapabilityMeta
from system.tools.domain_mapper import DomainMapper


def _parse_inline_meta(trailing: str) -> Dict[str, str]:
    """Parse inline [key=value] metadata from trailing text."""
    kv = {}
    if not trailing.strip():
        return kv
    # Updated regex to handle comma-separated pairs inside brackets
    pattern = r"([A-Za-z0-9_.\-:/]+)\s*=\s*([^,\]]+)"
    for key, value in re.findall(pattern, trailing):
        kv[key.strip()] = value.strip()
    return kv


def _iter_source_files(
    root: Path, include_globs: List[str], exclude_globs: List[str]
) -> Iterable[Path]:
    """Yields repository files to be scanned."""

    def wanted(p: Path) -> bool:
        """Return True if the path matches include_globs (if specified) or has a .py suffix, and does not match exclude_globs."""
        if any((p.match(g) for g in exclude_globs)):
            return False
        if include_globs:
            return any((p.match(g) for g in include_globs))
        return p.suffix in {".py"}

    for p in root.rglob("*"):
        if p.is_file() and wanted(p):
            yield p


def collect_from_source_scan(
    root: Path,
    include_globs: List[str],
    exclude_globs: List[str],
    domain_mapper: Optional[DomainMapper] = None,
) -> Dict[str, CapabilityMeta]:
    """
    Scans for '# CAPABILITY:' tags with optional inline metadata.
    Now constitution-aware via DomainMapper.
    """
    caps: Dict[str, CapabilityMeta] = {}

    # Create domain mapper if not provided for backward compatibility.
    if domain_mapper is None:
        domain_mapper = DomainMapper(root)

    # Use a regex that can handle both simple and metadata-rich capability tags.
    capability_re = re.compile(r"^\s*#\s*CAPABILITY:\s*([A-Za-z0-9_.\-:/]+)(.*)$")

    for file in _iter_source_files(root, include_globs, exclude_globs):
        try:
            content = file.read_text(encoding="utf-8", errors="ignore")
            for line in content.splitlines():
                m = capability_re.match(line)
                if not m:
                    continue

                cap = m.group(1).strip()
                trailing_text = m.group(2) or ""
                kv = _parse_inline_meta(trailing_text)

                # CRITICAL FIX: Use DomainMapper to determine domain if not provided inline.
                domain = kv.get("domain")
                if domain is None:
                    relative_path = file.relative_to(root)
                    domain = domain_mapper.determine_domain(relative_path)
                    if domain == "unassigned":
                        domain = None  # Standardize "unassigned" to None.

                caps[cap] = CapabilityMeta(
                    capability=cap, domain=domain, owner=kv.get("owner")
                )
        except Exception:
            continue
    return caps
