# src/mind/governance/checks/legacy_tag_check.py
"""
Enforces caps.id_format: Finds and forbids legacy '# CAPABILITY:' tags.
Legacy tags violate the current ID schema and must be migrated to '# ID: <uuid>'.
"""

from __future__ import annotations

import re
from pathlib import Path

from mind.governance.checks.base_check import BaseCheck
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)

# Strict pattern: Start of line (with indent), hash, explicit CAPABILITY keyword
LEGACY_TAG_PATTERN = re.compile(r"^\s*#\s*CAPABILITY:\s*\S+", re.IGNORECASE)

# Performance optimization: Only scan text-based code/config files
INTERESTING_EXTENSIONS = {".py", ".yaml", ".yml", ".sh", ".bash", ".md"}

# Exclude noise
EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "htmlcov",
    "dist",
    "build",
    "site-packages",
}


# ID: 0649c22b-9336-490b-9ffd-25e202924301
class LegacyTagCheck(BaseCheck):
    """
    Scans the codebase for legacy '# CAPABILITY:' tags.
    Ref: standard_code_general (caps.id_format)
    """

    policy_rule_ids = ["caps.id_format"]

    # ID: 94e602d4-47da-455d-be69-fe7a037bcb2b
    def execute(self) -> list[AuditFinding]:
        """
        Runs the check by scanning relevant text files for the legacy tag pattern.
        """
        findings = []

        # Optimization: If context has a file list, use it. Otherwise, scan intelligently.
        # Assuming context might not track all file types we care about (like bash),
        # we perform a controlled walk.

        files_to_scan = self._get_scannable_files()

        for file_path in files_to_scan:
            try:
                # Read as text
                content = file_path.read_text(encoding="utf-8")

                for i, line in enumerate(content.splitlines(), 1):
                    # Fast check before regex
                    if "CAPABILITY" in line:
                        if LEGACY_TAG_PATTERN.search(line):
                            findings.append(
                                AuditFinding(
                                    check_id="caps.id_format",
                                    severity=AuditSeverity.ERROR,
                                    message=(
                                        "Legacy '# CAPABILITY:' tag found. "
                                        "Replace with '# ID: <uuid>' per code standards."
                                    ),
                                    file_path=str(
                                        file_path.relative_to(self.repo_root)
                                    ),
                                    line_number=i,
                                    context={"legacy_line": line.strip()},
                                )
                            )
            except UnicodeDecodeError:
                # Not a text file (despite extension check), skip safely
                continue
            except Exception as e:
                logger.debug("Failed to scan %s for legacy tags: %s", file_path, e)
                continue

        return findings

    def _get_scannable_files(self) -> list[Path]:
        """
        Generates a list of files to scan, pruning directories efficiently.
        """
        scannable = []

        # Walk top-down so we can prune directories
        for root, dirs, files in self.repo_root.walk():
            # 1. Prune Excluded Directories in-place
            # This prevents descending into .git, .venv, etc.
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

            for file in files:
                file_path = root / file

                # 2. Check Extension
                if file_path.suffix not in INTERESTING_EXTENSIONS:
                    continue

                # 3. Check Specific File Exclusions
                if file in {"poetry.lock", "project_context.txt"}:
                    continue

                scannable.append(file_path)

        return scannable
