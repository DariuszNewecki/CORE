# src/mind/governance/checks/import_group_check.py
"""
Enforces layout.import_grouping via Ruff.
Scope: src/ and tests/
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from mind.governance.checks.base_check import BaseCheck
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)


# ID: 18776480-eaa4-4d61-b6dc-4f17059f7777
class ImportGroupCheck(BaseCheck):
    """
    Constitutional check for import grouping that delegates to Ruff.
    """

    policy_rule_ids = ["layout.import_grouping"]

    # ID: 5eb90564-22d8-4cb1-b208-086a6eaa143d
    def execute(self) -> list[AuditFinding]:
        """Execute import grouping check by delegating to Ruff."""
        findings = []

        # Determine paths to check based on existence
        paths_to_check = []
        if (self.repo_root / "src").exists():
            paths_to_check.append(str(self.repo_root / "src"))
        if (self.repo_root / "tests").exists():
            paths_to_check.append(str(self.repo_root / "tests"))

        if not paths_to_check:
            return findings

        try:
            # Run Ruff with isort rules (I)
            result = subprocess.run(
                [
                    "ruff",
                    "check",
                    *paths_to_check,  # Expand list of paths
                    "--select",
                    "I",  # Import sorting rules
                    "--output-format",
                    "json",
                    "--exit-zero",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.stdout:
                violations = json.loads(result.stdout)

                for violation in violations:
                    file_path = Path(violation.get("filename", ""))

                    try:
                        rel_path = file_path.relative_to(self.repo_root)
                    except ValueError:
                        rel_path = file_path

                    findings.append(
                        AuditFinding(
                            check_id="layout.import_grouping",
                            severity=AuditSeverity.WARNING,
                            message="Imports not properly grouped. Run `core-admin fix import-group`.",
                            file_path=str(rel_path),
                            line_number=violation.get("location", {}).get("row", 1),
                            context={
                                "ruff_code": violation.get("code", ""),
                                "ruff_message": violation.get("message", ""),
                                "fix_command": "core-admin fix import-group",
                            },
                        )
                    )

        except FileNotFoundError:
            logger.error("Ruff not found. Install with: pip install ruff")
        except json.JSONDecodeError as e:
            logger.error("Failed to parse Ruff output: %s", e)
        except Exception as e:
            logger.error("Import group check failed: %s", e)

        return findings
