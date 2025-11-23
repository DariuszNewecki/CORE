# src/features/introspection/discovery/from_source_scan.py
"""
Discovers implemented capabilities by performing a direct source code scan.
This is a fallback for when the knowledge graph is not available.
"""

from __future__ import annotations

import re
from pathlib import Path

from shared.models import CapabilityMeta

CAPABILITY_PATTERN = re.compile(r"#\s*CAPABILITY:\s*(\S+)")


# ID: 3fb50751-54f5-4282-9b52-fcc5eb6c23d2
def collect_from_source_scan(
    root: Path, include_globs: list[str], exclude_globs: list[str]
) -> dict[str, CapabilityMeta]:
    """
    Scans Python files for # CAPABILITY tags.
    """
    capabilities: dict[str, CapabilityMeta] = {}
    search_path = root / "src"

    files_to_scan = list(search_path.rglob("*.py"))

    for py_file in files_to_scan:
        try:
            content = py_file.read_text("utf-8")
            matches = CAPABILITY_PATTERN.findall(content)
            for cap_key in matches:
                if cap_key not in capabilities:
                    capabilities[cap_key] = CapabilityMeta(key=cap_key)
        except (OSError, UnicodeDecodeError):
            continue

    return capabilities
