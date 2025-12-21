# src/mind/governance/checks/legacy_tag_check.py
"""
Enforces caps.id_format: Finds and forbids legacy '# CAPABILITY:' tags.
Legacy tags violate the current ID schema and must be migrated to '# ID: <uuid>'.

Ref: .intent/charter/standards/code_standards.json
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, ClassVar

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.rule_enforcement_check import (
    EnforcementMethod,
    RuleEnforcementCheck,
)
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)

CODE_STANDARDS_POLICY = Path(".intent/charter/standards/code_standards.json")

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


# ID: legacy-tag-enforcement
# ID: fb25a39e-a205-421f-b8c0-056e3935e6ff
class LegacyTagEnforcement(EnforcementMethod):
    """
    Scans the codebase for legacy '# CAPABILITY:' tags.
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: bd193121-c494-455d-93ff-4ab85eafedf0
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        """
        Runs the check by scanning relevant text files for the legacy tag pattern.
        """
        findings = []

        files_to_scan = self._get_scannable_files(context)

        for file_path in files_to_scan:
            try:
                # Read as text
                content = file_path.read_text(encoding="utf-8")

                for i, line in enumerate(content.splitlines(), 1):
                    # Fast check before regex
                    if "CAPABILITY" in line:
                        if LEGACY_TAG_PATTERN.search(line):
                            findings.append(
                                self._create_finding(
                                    message=(
                                        "Legacy '# CAPABILITY:' tag found. "
                                        "Replace with '# ID: <uuid>' per code standards."
                                    ),
                                    file_path=str(
                                        file_path.relative_to(context.repo_path)
                                    ),
                                    line_number=i,
                                )
                            )
            except UnicodeDecodeError:
                # Not a text file (despite extension check), skip safely
                continue
            except Exception as e:
                logger.debug("Failed to scan %s for legacy tags: %s", file_path, e)
                continue

        return findings

    def _get_scannable_files(self, context: AuditorContext) -> list[Path]:
        """
        Generates a list of files to scan, pruning directories efficiently.
        """
        scannable = []

        # Walk top-down so we can prune directories
        for root, dirs, files in context.repo_path.walk():
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


# ID: 0649c22b-9336-490b-9ffd-25e202924301
class LegacyTagCheck(RuleEnforcementCheck):
    """
    Scans the codebase for legacy '# CAPABILITY:' tags.

    Ref: .intent/charter/standards/code_standards.json
    """

    policy_rule_ids: ClassVar[list[str]] = ["caps.id_format"]

    policy_file: ClassVar[Path] = CODE_STANDARDS_POLICY

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        LegacyTagEnforcement(rule_id="caps.id_format"),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
