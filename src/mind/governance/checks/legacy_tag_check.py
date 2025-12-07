# src/mind/governance/checks/legacy_tag_check.py
"""
A constitutional audit check to find and forbid legacy '# CAPABILITY:' tags,
enforcing the 'caps.id_format' rule from the code_standards policy.
"""

from __future__ import annotations

import re
from pathlib import Path

from mind.governance.checks.base_check import BaseCheck
from shared.models import AuditFinding, AuditSeverity


# --- START OF FIX ---
# This pattern is now more specific. It requires the line to start with the tag
# and to be followed by at least one non-whitespace character (the key).
LEGACY_TAG_PATTERN = re.compile(r"^\s*#\s*CAPABILITY:\s*\S+", re.IGNORECASE)
# --- END OF FIX ---

EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "reports",
}
EXCLUDE_FILES = {"poetry.lock", "project_context.txt"}
BINARY_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".pyc",
    ".so",
    ".o",
    ".zip",
    ".gz",
    ".pdf",
}


# ID: 0649c22b-9336-490b-9ffd-25e202924301
class LegacyTagCheck(BaseCheck):
    """
    Scans the codebase to ensure no legacy '# CAPABILITY:' tags remain,
    thereby enforcing the constitutionally mandated '# ID:' format.
    """

    # Fulfills the contract from BaseCheck.
    policy_rule_ids = ["caps.id_format"]

    # ID: 94e602d4-47da-455d-be69-fe7a037bcb2b
    def execute(self) -> list[AuditFinding]:
        """
        Runs the check by scanning all non-excluded files for the legacy tag pattern.
        """
        findings = []
        for file_path in self.repo_root.rglob("*"):
            if not self._is_scannable(file_path):
                continue

            try:
                content = file_path.read_text(encoding="utf-8")
                for i, line in enumerate(content.splitlines(), 1):
                    if LEGACY_TAG_PATTERN.search(line):
                        findings.append(
                            AuditFinding(
                                # The check_id now matches the constitution exactly.
                                check_id="caps.id_format",
                                severity=AuditSeverity.ERROR,
                                message="Legacy '# CAPABILITY:' tag found. Please replace with '# ID: <uuid>'.",
                                file_path=str(file_path.relative_to(self.repo_root)),
                                line_number=i,
                            )
                        )
            except (UnicodeDecodeError, OSError):
                # Silently ignore files that can't be read (e.g., broken symlinks)
                continue
        return findings

    def _is_scannable(self, file_path: Path) -> bool:
        """Helper method to determine if a file should be scanned."""
        if not file_path.is_file():
            return False
        if file_path.name in EXCLUDE_FILES:
            return False
        if file_path.suffix in BINARY_EXTENSIONS:
            return False
        # Check if any part of the path is in the exclude list
        if any(part in EXCLUDE_DIRS for part in file_path.parts):
            return False
        return True
