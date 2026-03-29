# src/shared/self_healing/remediation_interpretation/finding_normalizer.py

from __future__ import annotations

from typing import Any

from shared.self_healing.remediation_interpretation.models import NormalizedFinding


# ID: 5f3f6c39-2d8a-4b97-a6a0-4e97c2b7e9f1
class FindingNormalizer:
    """
    Normalize claimed blackboard findings into a deterministic internal shape.

    This service operates downstream of AuditViolationSensor. The sensor is
    responsible for converting heterogeneous audit-engine outputs into stable
    blackboard findings. FindingNormalizer converts those claimed blackboard
    entries into NormalizedFinding objects for architectural interpretation.

    Input contract:
        list[dict[str, Any]] where each item resembles:
        {
            "id": "...",
            "subject": "audit.violation::<rule_id>::<file_path>",
            "payload": {
                "rule_namespace": "...",
                "rule": "...",
                "file_path": "...",
                "line_number": ...,
                "message": "...",
                "severity": "...",
                "dry_run": ...,
                "status": "unprocessed",
                ...
            }
        }

    Design principles:
    - deterministic
    - tolerant of partial payload degradation
    - no database access
    - no file access
    - no LLM
    """

    # ID: 9f0a9271-3d9b-46ff-a23f-93c415d3f1bb
    def normalize(self, findings: list[dict[str, Any]]) -> list[NormalizedFinding]:
        """
        Normalize a batch of claimed blackboard findings.

        The result is sorted deterministically by:
        1. file_path
        2. line_number (None last)
        3. rule_id
        4. message
        5. finding_id
        """
        normalized = [self.normalize_one(item) for item in findings]
        normalized.sort(key=self._sort_key)
        return normalized

    # ID: 8d46de48-2c59-4936-bf06-7f6951a6f824
    def normalize_one(self, finding: dict[str, Any]) -> NormalizedFinding:
        """Normalize one claimed blackboard finding."""
        payload = finding.get("payload") or {}
        subject = str(finding.get("subject") or "")
        finding_id = str(finding.get("id") or "")

        subject_rule_id, subject_file_path = self._parse_subject(subject)

        rule_id = self._coerce_str(
            payload.get("rule"),
            fallback=subject_rule_id or "unknown.rule",
        )
        rule_namespace = self._infer_rule_namespace(
            payload.get("rule_namespace"),
            rule_id,
        )
        file_path = self._coerce_str(
            payload.get("file_path"),
            fallback=subject_file_path or "__unknown__",
        )
        line_number = self._coerce_optional_int(payload.get("line_number"))
        message = self._coerce_str(payload.get("message"), fallback="")
        severity = self._coerce_severity(payload.get("severity"))
        dry_run = bool(payload.get("dry_run", True))

        raw_context = self._extract_context(payload)

        return NormalizedFinding(
            finding_id=finding_id,
            subject=subject,
            rule_id=rule_id,
            rule_namespace=rule_namespace,
            file_path=file_path,
            line_number=line_number,
            message=message,
            severity=severity,
            dry_run=dry_run,
            raw_payload=dict(payload),
            raw_context=raw_context,
        )

    # ID: 27d0cdb8-c449-4dc0-a886-798c00a295a4
    def _sort_key(self, finding: NormalizedFinding) -> tuple[str, int, str, str, str]:
        """Deterministic sort key for normalized findings."""
        line_value = (
            finding.line_number if finding.line_number is not None else 999_999_999
        )
        return (
            finding.file_path,
            line_value,
            finding.rule_id,
            finding.message,
            finding.finding_id,
        )

    # ID: 0f630c9c-b5a1-4b3b-8887-e0a21e1a84d4
    def _parse_subject(self, subject: str) -> tuple[str | None, str | None]:
        """
        Parse blackboard subject of the form:
            audit.violation::<rule_id>::<file_path>

        Returns:
            (rule_id, file_path)
        """
        if not subject:
            return None, None

        parts = subject.split("::", 2)
        if len(parts) != 3:
            return None, None

        prefix, rule_id, file_path = parts
        if prefix != "audit.violation":
            return None, None

        return (rule_id or None, file_path or None)

    # ID: d7d7abec-6d94-4890-b7e2-cba9a4b6fbd1
    def _infer_rule_namespace(self, explicit_namespace: Any, rule_id: str) -> str:
        """
        Determine the rule namespace.

        Preference order:
        1. payload.rule_namespace if present
        2. derive from rule_id by dropping the last dotted segment
        3. use rule_id as-is
        """
        namespace = self._coerce_str(explicit_namespace, fallback="")
        if namespace:
            return namespace

        if "." in rule_id:
            return rule_id.rsplit(".", 1)[0]

        return rule_id

    # ID: 7498a8cb-0b18-45d3-9f48-4f7f0c8a6298
    def _extract_context(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Preserve any contextual payload fields not part of the core normalized
        contract. This supports forward compatibility and traceability.

        The current AuditViolationSensor payload may not include a dedicated
        'context' field, but this method is intentionally future-proof.
        """
        context_value = payload.get("context")
        if isinstance(context_value, dict):
            return dict(context_value)

        reserved = {
            "rule_namespace",
            "rule",
            "file_path",
            "line_number",
            "message",
            "severity",
            "dry_run",
            "status",
        }

        extra = {key: value for key, value in payload.items() if key not in reserved}
        return extra

    # ID: 23de5321-8e85-4a59-a62a-e7c7d43a7c58
    def _coerce_str(self, value: Any, fallback: str = "") -> str:
        """Coerce arbitrary value to trimmed string."""
        if value is None:
            return fallback
        text = str(value).strip()
        return text if text else fallback

    # ID: a24a11a0-5f8f-4f1c-8b54-85b9837434fd
    def _coerce_optional_int(self, value: Any) -> int | None:
        """Coerce an optional integer-like value."""
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    # ID: 2329c45c-52d5-4f9d-bf5f-8f35f2c2a67d
    def _coerce_severity(self, value: Any) -> str:
        """
        Normalize severity values into a stable lowercase set where possible.

        Unknown severities are preserved as lowercased strings rather than
        rejected, because the interpretation layer should be resilient to
        future policy expansion.
        """
        text = self._coerce_str(value, fallback="warning").lower()

        aliases = {
            "warn": "warning",
            "err": "error",
            "crit": "critical",
        }

        return aliases.get(text, text)
