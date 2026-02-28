# src/cli/logic/legacy_scan_logic.py
# ID: a1f2e3d4-b5c6-7890-abcd-ef1234567abc

"""
Legacy Scanner Logic - Pure read-only analysis.

Scans the codebase for markers that indicate technical debt:
workarounds, healed violations, circular import patches,
deprecated code, and unresolved TODOs.

Constitutional Alignment:
- Phase: PARSE (read-only fact extraction)
- Authority: CODE (structural analysis)
- Boundary: Accepts repo_root parameter (no settings access)
- No side effects: same input → same output
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Marker definitions — the map of what we're hunting
# ---------------------------------------------------------------------------

LEGACY_MARKERS: dict[str, dict] = {
    "HEALED": {
        "label": "Healed Violation",
        "description": "Was broken, patched in-place. Candidate for proper fix.",
        "severity": "high",
        "color": "red",
    },
    "CONSTITUTIONAL FIX": {
        "label": "Constitutional Fix",
        "description": "Layer boundary violation patched inline. Needs architectural resolution.",
        "severity": "high",
        "color": "red",
    },
    "CIRCULARITY FIX": {
        "label": "Circularity Fix",
        "description": "Circular import resolved with late import hack. Needs structural fix.",
        "severity": "high",
        "color": "red",
    },
    "DEPRECATED": {
        "label": "Deprecated",
        "description": "Kept for compatibility. Safe to delete after confirming no callers.",
        "severity": "medium",
        "color": "yellow",
    },
    "WORKAROUND": {
        "label": "Workaround",
        "description": "Known bad solution. Needs a real fix.",
        "severity": "high",
        "color": "red",
    },
    "LEGACY": {
        "label": "Legacy",
        "description": "Old pattern kept alive. Review for removal.",
        "severity": "medium",
        "color": "yellow",
    },
    "TODO": {
        "label": "TODO",
        "description": "Unfinished work. May be blocking or just aspirational.",
        "severity": "low",
        "color": "blue",
    },
    "FIXME": {
        "label": "FIXME",
        "description": "Known broken or fragile. Needs attention.",
        "severity": "high",
        "color": "red",
    },
    "HACK": {
        "label": "Hack",
        "description": "Intentionally dirty solution. Needs cleanup.",
        "severity": "high",
        "color": "red",
    },
    "TEMP": {
        "label": "Temporary",
        "description": "Meant to be short-lived. Likely overstayed its welcome.",
        "severity": "medium",
        "color": "yellow",
    },
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
# ID: b2c3d4e5-f6a7-8901-bcde-f01234567bcd
class LegacyHit:
    """A single legacy marker found in the codebase."""

    file_path: str
    line_number: int
    marker: str
    line_content: str
    severity: str
    label: str
    color: str


@dataclass
# ID: c3d4e5f6-a7b8-9012-cdef-012345678cde
class FileLegacySummary:
    """Aggregated legacy findings for a single file."""

    file_path: str
    hits: list[LegacyHit] = field(default_factory=list)

    @property
    # ID: d4e5f6a7-b8c9-0123-defa-0123456789de
    def total(self) -> int:
        return len(self.hits)

    @property
    # ID: e5f6a7b8-c9d0-1234-efab-123456789012
    def high_severity_count(self) -> int:
        return sum(1 for h in self.hits if h.severity == "high")

    @property
    # ID: f6a7b8c9-d0e1-2345-fabc-23456789012f
    def by_marker(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for hit in self.hits:
            counts[hit.marker] = counts.get(hit.marker, 0) + 1
        return counts


@dataclass
# ID: a7b8c9d0-e1f2-3456-abcd-34567890123a
class LegacyScanResult:
    """Complete scan result across all files."""

    repo_root: str
    files_scanned: int
    files_with_hits: list[FileLegacySummary] = field(default_factory=list)

    @property
    # ID: b8c9d0e1-f2a3-4567-bcde-45678901234b
    def total_hits(self) -> int:
        return sum(f.total for f in self.files_with_hits)

    @property
    # ID: c9d0e1f2-a3b4-5678-cdef-56789012345c
    def total_high_severity(self) -> int:
        return sum(f.high_severity_count for f in self.files_with_hits)

    @property
    # ID: d0e1f2a3-b4c5-6789-defa-67890123456d
    def marker_totals(self) -> dict[str, int]:
        totals: dict[str, int] = {}
        for f in self.files_with_hits:
            for marker, count in f.by_marker.items():
                totals[marker] = totals.get(marker, 0) + count
        return dict(sorted(totals.items(), key=lambda x: x[1], reverse=True))

    @property
    # ID: e1f2a3b4-c5d6-7890-efab-78901234567e
    def files_sorted_by_debt(self) -> list[FileLegacySummary]:
        """Files sorted by high-severity count descending, then total."""
        return sorted(
            self.files_with_hits,
            key=lambda f: (f.high_severity_count, f.total),
            reverse=True,
        )


# ---------------------------------------------------------------------------
# Scanner — pure function, no side effects
# ---------------------------------------------------------------------------


# ID: f2a3b4c5-d6e7-8901-fabc-890123456789
def scan_for_legacy_markers(
    repo_root: Path,
    scan_dirs: list[str] | None = None,
    severity_filter: str | None = None,
) -> LegacyScanResult:
    """
    Scan Python source files for legacy/debt markers.

    Args:
        repo_root: Repository root path.
        scan_dirs: Subdirectories to scan (default: ["src"]).
        severity_filter: If set, only return hits of this severity
                         ("high", "medium", "low").

    Returns:
        LegacyScanResult with all findings, sortable by debt load.
    """
    if scan_dirs is None:
        scan_dirs = ["src"]

    # Build one combined regex that matches any marker (case-insensitive)
    pattern = re.compile(
        r"#.*\b(" + "|".join(re.escape(m) for m in LEGACY_MARKERS) + r")\b",
        re.IGNORECASE,
    )

    files_scanned = 0
    file_summaries: list[FileLegacySummary] = []

    for scan_dir in scan_dirs:
        target = repo_root / scan_dir
        if not target.exists():
            continue

        for py_file in sorted(target.rglob("*.py")):
            # Skip __pycache__ and .venv
            parts = py_file.parts
            if any(p in ("__pycache__", ".venv", ".git") for p in parts):
                continue

            files_scanned += 1
            summary = _scan_file(py_file, repo_root, pattern, severity_filter)
            if summary.hits:
                file_summaries.append(summary)

    return LegacyScanResult(
        repo_root=str(repo_root),
        files_scanned=files_scanned,
        files_with_hits=file_summaries,
    )


# ID: a3b4c5d6-e7f8-9012-abcd-901234567890
def _scan_file(
    file_path: Path,
    repo_root: Path,
    pattern: re.Pattern,
    severity_filter: str | None,
) -> FileLegacySummary:
    """Scan a single file and return its legacy summary."""
    rel_path = str(file_path.relative_to(repo_root))
    summary = FileLegacySummary(file_path=rel_path)

    try:
        lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return summary

    for line_num, line in enumerate(lines, start=1):
        match = pattern.search(line)
        if not match:
            continue

        # Identify which marker was matched (use uppercase for lookup)
        matched_text = match.group(1).upper()

        # Find the canonical marker key (handles partial matches)
        marker_key = _resolve_marker(matched_text)
        if not marker_key:
            continue

        info = LEGACY_MARKERS[marker_key]

        if severity_filter and info["severity"] != severity_filter:
            continue

        summary.hits.append(
            LegacyHit(
                file_path=rel_path,
                line_number=line_num,
                marker=marker_key,
                line_content=line.strip()[:120],  # Truncate for display
                severity=info["severity"],
                label=info["label"],
                color=info["color"],
            )
        )

    return summary


# ID: b4c5d6e7-f8a9-0123-bcde-012345678901
def _resolve_marker(text: str) -> str | None:
    """Match detected text to a canonical marker key."""
    # Direct match first
    if text in LEGACY_MARKERS:
        return text
    for key in LEGACY_MARKERS:
        if text in key or key in text:
            return key
    return None


# ID: c5d6e7f8-a9b0-1234-cdef-123456789012
def get_top_debt_files(
    result: LegacyScanResult, limit: int = 10
) -> list[FileLegacySummary]:
    """Return the files with the highest debt load."""
    return result.files_sorted_by_debt[:limit]
