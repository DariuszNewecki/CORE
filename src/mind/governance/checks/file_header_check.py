# src/mind/governance/checks/file_header_check.py
"""
Enforces layout.src_module_header: Every Python module under src/ must start with canonical file path comment.

Ref: .intent/charter/standards/code_standards.json
"""

from __future__ import annotations

from typing import Any, ClassVar

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.rule_enforcement_check import (
    EnforcementMethod,
    RuleEnforcementCheck,
)
from shared.config import settings
from shared.models import AuditFinding


# ID: file-header-enforcement
# ID: c1d2e3f4-a5b6-4c7d-8e9f-0a1b2c3d4e5f
class FileHeaderEnforcement(EnforcementMethod):
    """Verifies that Python modules have correct file path headers."""

    # ID: 6d6bc3f4-ccfa-4d96-97f7-cffc34dd24b1
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        findings = []

        for file_path in context.python_files:
            try:
                rel_path = file_path.relative_to(context.repo_path)
                posix_path = rel_path.as_posix()

                if not posix_path.startswith("src/"):
                    continue

                expected_header = f"# {posix_path}"

                with file_path.open("r", encoding="utf-8") as f:
                    first_line = f.readline().rstrip()

                if first_line != expected_header:
                    findings.append(
                        self._create_finding(
                            message=f"Missing or incorrect header. Expected: {expected_header}",
                            file_path=str(rel_path),
                            line_number=1,
                        )
                    )

            except Exception:
                pass  # Skip files that can't be read

        return findings


# ID: a0e5a8b7-2068-4e02-bfd6-58cfa11a6631
class FileHeaderCheck(RuleEnforcementCheck):
    """
    Enforces layout.src_module_header.
    Ref: .intent/charter/standards/code_standards.json
    """

    policy_rule_ids: ClassVar[list[str]] = ["layout.src_module_header"]

    policy_file: ClassVar = settings.paths.policy("code_standards")

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        FileHeaderEnforcement(rule_id="layout.src_module_header"),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
