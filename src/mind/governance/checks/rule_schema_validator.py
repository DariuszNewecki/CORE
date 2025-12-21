# src/mind/governance/checks/rule_schema_validator.py

"""
Validates all constitutional rules against the official rule schema.
Enforces schema compliance for .intent/charter/standards/**/*.json files.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import jsonschema
import yaml

from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext

logger = getLogger(__name__)


# ID: a8b9c1d2-e3f4-5678-90ab-cdef12345678
class RuleSchemaValidator:
    """Validates constitutional rules against rule_schema.yaml."""

    CHECK_ID = "meta.rule_schema_compliance"

    def __init__(self, context: AuditorContext):
        self.context = context
        self.schema_path = context.intent_path / "charter/schemas/rule_schema.json"
        self.standards_path = context.intent_path / "charter/standards"
        self.schema: dict | None = None

    # ID: b5a2bd1b-b81e-45bf-b4ed-1f8b6a96ad35
    def execute(self) -> list[AuditFinding]:
        """Execute schema validation on all rule files."""
        findings: list[AuditFinding] = []

        # Load schema
        if not self.schema_path.exists():
            return [
                AuditFinding(
                    check_id=self.CHECK_ID,
                    severity=AuditSeverity.ERROR,
                    message="Rule schema not found at .intent/charter/schemas/rule_schema.json",
                    file_path=str(self.schema_path.relative_to(self.context.repo_path)),
                )
            ]

        try:
            with open(self.schema_path, encoding="utf-8") as f:
                self.schema = yaml.safe_load(f)
        except Exception as e:
            return [
                AuditFinding(
                    check_id=self.CHECK_ID,
                    severity=AuditSeverity.ERROR,
                    message=f"Failed to load rule schema: {e}",
                    file_path=str(self.schema_path.relative_to(self.context.repo_path)),
                )
            ]

        # Find all rule files
        if not self.standards_path.exists():
            return [
                AuditFinding(
                    check_id=self.CHECK_ID,
                    severity=AuditSeverity.ERROR,
                    message="Standards directory not found at .intent/charter/standards/",
                    file_path=str(
                        self.standards_path.relative_to(self.context.repo_path)
                    ),
                )
            ]

        rule_files = list(self.standards_path.rglob("*.yaml"))

        for rule_file in rule_files:
            findings.extend(self._validate_file(rule_file))

        return findings

    def _validate_file(self, rule_file: Path) -> list[AuditFinding]:
        """Validate a single rule file against schema."""
        findings: list[AuditFinding] = []
        rel_path = str(rule_file.relative_to(self.context.repo_path))

        try:
            with open(rule_file, encoding="utf-8") as f:
                content = yaml.safe_load(f)
        except Exception as e:
            return [
                AuditFinding(
                    check_id=self.CHECK_ID,
                    severity=AuditSeverity.ERROR,
                    message=f"Failed to parse YAML: {e}",
                    file_path=rel_path,
                )
            ]

        # Handle both single rule and list of rules
        rules = content if isinstance(content, list) else [content]

        for idx, rule in enumerate(rules):
            if not isinstance(rule, dict):
                findings.append(
                    AuditFinding(
                        check_id=self.CHECK_ID,
                        severity=AuditSeverity.ERROR,
                        message=f"Rule {idx} is not a dictionary",
                        file_path=rel_path,
                    )
                )
                continue

            # Validate against JSON Schema
            try:
                jsonschema.validate(instance=rule, schema=self.schema)
            except jsonschema.ValidationError as e:
                findings.append(
                    AuditFinding(
                        check_id=self.CHECK_ID,
                        severity=AuditSeverity.ERROR,
                        message=f"Schema violation in rule '{rule.get('id', f'index-{idx}')}': {e.message}",
                        file_path=rel_path,
                        context={
                            "rule_id": rule.get("id", f"index-{idx}"),
                            "schema_path": list(e.absolute_path),
                            "validator": e.validator,
                        },
                    )
                )
            except jsonschema.SchemaError as e:
                findings.append(
                    AuditFinding(
                        check_id=self.CHECK_ID,
                        severity=AuditSeverity.ERROR,
                        message=f"Invalid schema definition: {e.message}",
                        file_path=rel_path,
                    )
                )

        return findings


# Fix the main() function - severity is already a string


# ID: ad7e76f7-b6ea-4c65-a140-1ec9d71e890c
async def main():
    """Standalone execution."""
    repo_path = Path.cwd()

    # Import here to avoid circular dependencies
    from mind.governance.audit_context import AuditorContext

    context = AuditorContext(repo_path)
    validator = RuleSchemaValidator(context)
    findings = validator.execute()

    if not findings:
        print("✓ All rules comply with schema")
        sys.exit(0)

    print(f"✗ Found {len(findings)} violations:\n")
    for f in findings:
        severity_str = (
            f.severity.name if hasattr(f.severity, "name") else str(f.severity)
        )
        print(f"  {severity_str}: {f.message}")
        print(f"    File: {f.file_path}\n")

    sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
