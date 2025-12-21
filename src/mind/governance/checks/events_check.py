# src/mind/governance/checks/events_check.py
"""
Enforces event schema standards: CloudEvents compliance, topic naming, payload immutability.

Ref: .intent/charter/standards/architecture/event_schema_standard.json
"""

from __future__ import annotations

import ast
from typing import Any, ClassVar

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.rule_enforcement_check import (
    EnforcementMethod,
    RuleEnforcementCheck,
)
from shared.config import settings
from shared.models import AuditFinding, AuditSeverity


# ID: events-cloudevents-enforcement
# ID: f4a5b6c7-d8e9-4f0a-1b2c-3d4e5f6a7b8c
class CloudEventsEnforcement(EnforcementMethod):
    """Verifies CloudEvents compliance in event definitions."""

    # ID: 53fa1a37-9781-4e14-9190-ceac6308728c
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        findings = []

        # Look for event schema definitions
        events_dir = context.repo_path / "src" / "shared" / "events"
        if not events_dir.exists():
            return findings

        required_fields = ["id", "source", "type", "data"]

        for file_path in events_dir.rglob("*.py"):
            try:
                content = file_path.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=str(file_path))

                # Look for dataclass definitions
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        # Check if it has @dataclass decorator
                        has_dataclass = any(
                            (
                                (isinstance(dec, ast.Name) and dec.id == "dataclass")
                                or (
                                    isinstance(dec, ast.Attribute)
                                    and dec.attr == "dataclass"
                                )
                            )
                            for dec in node.decorator_list
                        )

                        if has_dataclass and "Event" in node.name:
                            # Check for required CloudEvents fields
                            field_names = []
                            for item in node.body:
                                if isinstance(item, ast.AnnAssign) and isinstance(
                                    item.target, ast.Name
                                ):
                                    field_names.append(item.target.id)

                            missing = set(required_fields) - set(field_names)
                            if missing:
                                findings.append(
                                    self._create_finding(
                                        message=f"Event class {node.name} missing CloudEvents fields: {missing}",
                                        file_path=str(
                                            file_path.relative_to(context.repo_path)
                                        ),
                                        line_number=node.lineno,
                                    )
                                )

            except Exception:
                pass

        return findings


# ID: a5b6c7d8-e9f0-4a1b-2c3d-4e5f6a7b8c9d
class TopicNamingEnforcement(EnforcementMethod):
    """Verifies event topic naming conventions."""

    # ID: 2e06d3b7-bc05-44a9-9cd8-c638b55501c8
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        findings = []

        # Look for topic definitions in event files
        events_dir = context.repo_path / "src" / "shared" / "events"
        if not events_dir.exists():
            return findings

        for file_path in events_dir.rglob("*.py"):
            try:
                content = file_path.read_text(encoding="utf-8")

                # Look for TOPIC constants
                if "TOPIC" in content:
                    lines = content.splitlines()
                    for i, line in enumerate(lines, 1):
                        if "TOPIC" in line and "=" in line:
                            # Check naming convention: domain.entity.action
                            if '"' in line or "'" in line:
                                topic_value = (
                                    line.split("=")[1].strip().strip('"').strip("'")
                                )
                                parts = topic_value.split(".")
                                if len(parts) != 3:
                                    findings.append(
                                        self._create_finding(
                                            message=f"Topic naming violation. Expected format: domain.entity.action, got: {topic_value}",
                                            file_path=str(
                                                file_path.relative_to(context.repo_path)
                                            ),
                                            line_number=i,
                                        )
                                    )

            except Exception:
                pass

        return findings


# ID: b6c7d8e9-f0a1-4b2c-3d4e-5f6a7b8c9d0e
class PayloadImmutabilityEnforcement(EnforcementMethod):
    """Verifies that event payloads are immutable (frozen dataclasses)."""

    # ID: 281b33f2-ff7b-47a3-a8d3-a72427e506f4
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        findings = []

        events_dir = context.repo_path / "src" / "shared" / "events"
        if not events_dir.exists():
            return findings

        for file_path in events_dir.rglob("*.py"):
            try:
                content = file_path.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=str(file_path))

                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef) and "Event" in node.name:
                        # Check if dataclass has frozen=True
                        is_frozen = False
                        for dec in node.decorator_list:
                            if isinstance(dec, ast.Call):
                                # Check for @dataclass(frozen=True)
                                for keyword in dec.keywords:
                                    if (
                                        keyword.arg == "frozen"
                                        and isinstance(keyword.value, ast.Constant)
                                        and keyword.value.value is True
                                    ):
                                        is_frozen = True

                        if not is_frozen:
                            findings.append(
                                self._create_finding(
                                    message=f"Event class {node.name} must be frozen (immutable). Use @dataclass(frozen=True)",
                                    file_path=str(
                                        file_path.relative_to(context.repo_path)
                                    ),
                                    line_number=node.lineno,
                                )
                            )

            except Exception:
                pass

        return findings


# ID: e7c4d3b2-a1f0-4e9d-8c7b-6a5f4e3d2c1b
class EventsCheck(RuleEnforcementCheck):
    """
    Enforces event schema standards.
    Ref: .intent/charter/standards/architecture/event_schema_standard.json
    """

    policy_rule_ids: ClassVar[list[str]] = [
        "events.cloudevents_compliance",
        "events.topic_naming",
        "events.payload_immutability",
    ]

    policy_file: ClassVar = settings.paths.policy("event_schema_standard")

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        CloudEventsEnforcement(
            rule_id="events.cloudevents_compliance", severity=AuditSeverity.ERROR
        ),
        TopicNamingEnforcement(
            rule_id="events.topic_naming", severity=AuditSeverity.WARNING
        ),
        PayloadImmutabilityEnforcement(
            rule_id="events.payload_immutability", severity=AuditSeverity.ERROR
        ),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
