# src/features/governance/checks/legacy_tag_check.py
from __future__ import annotations

import re

from features.governance.checks.base_check import BaseCheck
from shared.models import AuditFinding, AuditSeverity


# ID: 0649c22b-9336-490b-9ffd-25e202924301
class LegacyTagCheck(BaseCheck):
    # ID: 94e602d4-47da-455d-be69-fe7a037bcb2b
    def execute(self) -> list[AuditFinding]:
        findings = []
        pattern = re.compile(r"#\s*CAPABILITY:", re.IGNORECASE)
        exclude_dirs = {
            ".git",
            ".venv",
            "__pycache__",
            ".pytest_cache",
            ".ruff_cache",
            "reports",
        }
        exclude_files = {"poetry.lock", "project_context.txt"}
        binary_extensions = {
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

        # --- THIS IS THE FIX ---
        # The loop now correctly uses self.repo_root, which is set by the BaseCheck parent class.
        for file_path in self.repo_root.rglob("*"):
            if not file_path.is_file():
                continue

            if any(part in exclude_dirs for part in file_path.parts):
                continue
            if file_path.name in exclude_files:
                continue
            if file_path.suffix in binary_extensions:
                continue

            try:
                content = file_path.read_text(encoding="utf-8")
                for i, line in enumerate(content.splitlines(), 1):
                    if pattern.search(line):
                        findings.append(
                            AuditFinding(
                                check_id="style.no_legacy_capability_tags",
                                severity=AuditSeverity.ERROR,
                                file_path=str(file_path.relative_to(self.repo_root)),
                                line_number=i,
                            )
                        )
            except UnicodeDecodeError:
                continue
            except Exception:
                continue

        return findings
