# src/cli/logic/legacy_scan_logic.py

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

from shared.infrastructure.intent.operational_config import load_operational_config


_CFG = load_operational_config().misc


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
    "FUTURE": {
        "label": "FUTURE",
        "description": "Unfinished work. May be blocking or just aspirational.",
        "severity": "low",
        "color": "blue",
    },
    "PENDING": {
        "label": "PENDING",
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
# ID: d6932e42-9c0e-479f-b042-7a5ad17de1dd
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
# ID: 797b7f25-34cc-431e-8063-8deb7e904a4a
class FileLegacySummary:
    """Aggregated legacy findings for a single file."""

    file_path: str
    hits: list[LegacyHit] = field(default_factory=list)

    @property
    # ID: 5008a726-aadb-43ea-be8e-3153e6fa2d29
    def total(self) -> int:
        return len(self.hits)

    @property
    # ID: b1c73510-9dd9-447b-a805-bdce8c27dc8b
    def high_severity_count(self) -> int:
        return sum(1 for h in self.hits if h.severity == "high")

    @property
    # ID: bc53fc4b-12ea-4d80-8a5c-0d555a4c9a5a
    def by_marker(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for hit in self.hits:
            counts[hit.marker] = counts.get(hit.marker, 0) + 1
        return counts


@dataclass
# ID: f2b34317-d76f-4afd-a188-4a51f4c65062
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
    # ID: b7bde035-781c-4384-9585-46d0b6aef5d8
    def total_high_severity(self) -> int:
        return sum(f.high_severity_count for f in self.files_with_hits)

    @property
    # ID: f4cd1872-39ea-4f64-8967-fcbff6ce3716
    def marker_totals(self) -> dict[str, int]:
        totals: dict[str, int] = {}
        for f in self.files_with_hits:
            for marker, count in f.by_marker.items():
                totals[marker] = totals.get(marker, 0) + count
        return dict(sorted(totals.items(), key=lambda x: x[1], reverse=True))

    @property
    # ID: 8c14107d-b3e9-4281-a646-659e3b151a86
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


# ID: e53aa020-88f5-4981-8b74-6cf511f249ae
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


# ID: ef97c826-075a-4e40-b82a-5e3f34e406a0
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


# ID: e9e42775-7dfb-4a03-883f-77349a8f3f80
def _resolve_marker(text: str) -> str | None:
    """Match detected text to a canonical marker key."""
    # Direct match first
    if text in LEGACY_MARKERS:
        return text
    for key in LEGACY_MARKERS:
        if text in key or key in text:
            return key
    return None


# ID: 912933d9-7ef8-41cc-9959-7ab90418641b
def get_top_debt_files(
    result: LegacyScanResult, limit: int = _CFG.legacy_scan_display_limit
) -> list[FileLegacySummary]:
    """Return the files with the highest debt load."""
    return result.files_sorted_by_debt[:limit]
