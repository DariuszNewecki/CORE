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


# ID: 69b2d864-dc55-46c7-b81c-56812281a02c
class RuleSchemaValidator:
    """Validates constitutional rules against rule_schema.yaml."""

    CHECK_ID = "meta.rule_schema_compliance"

    def __init__(self, context: AuditorContext):
        self.context = context
        self.schema_path = context.intent_path / "charter/schemas/rule_schema.json"
        self.standards_path = context.intent_path / "charter/standards"
        self.schema: dict | None = None

    # ID: 49ed3e16-efb1-4b86-9fd9-0379152b056c
    def execute(self) -> list[AuditFinding]:
        """Execute schema validation on all rule files."""
        findings: list[AuditFinding] = []
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


# ID: 81998bdc-2297-4210-829e-95135f3d62a2
async def main():
    """Standalone execution."""
    repo_path = Path.cwd()
    from mind.governance.audit_context import AuditorContext

    context = AuditorContext(repo_path)
    validator = RuleSchemaValidator(context)
    findings = validator.execute()
    if not findings:
        logger.info("✓ All rules comply with schema")
        sys.exit(0)
    logger.info("✗ Found %s violations:\n", len(findings))
    for f in findings:
        severity_str = (
            f.severity.name if hasattr(f.severity, "name") else str(f.severity)
        )
        logger.info("  %s: %s", severity_str, f.message)
        logger.info("    File: %s\n", f.file_path)
    sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
