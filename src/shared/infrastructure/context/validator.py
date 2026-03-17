# src/shared/infrastructure/context/validator.py

"""
ContextValidator - enforces ContextPacket schema compliance.

Validates doctrine-aligned packets with sections:
    header
    phase
    constitution
    policy
    constraints
    evidence
    runtime
    provenance
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

import yaml

from shared.config import settings
from shared.logger import getLogger
from shared.models.validation_result import ValidationResult


logger = getLogger(__name__)


# ID: 9aba6527-289c-4511-8283-36074d5de950
class ContextValidator:
    """Validates ContextPacket packets against the runtime schema."""

    _REQUIRED_HEADER_FIELDS: ClassVar[set[str]] = {
        "packet_id",
        "created_at",
        "builder_version",
        "privacy",
        "mode",
        "goal",
        "trigger",
    }

    _ALLOWED_PRIVACY_VALUES: ClassVar[set[str]] = {"local_only", "remote_allowed"}
    _ALLOWED_PHASE_VALUES: ClassVar[set[str]] = {
        "parse",
        "load",
        "audit",
        "runtime",
        "execution",
    }
    _ALLOWED_ITEM_TYPES: ClassVar[set[str]] = {
        "symbol",
        "snippet",
        "summary",
        "dependency",
        "test",
        "signature",
        "code",
        "semantic_match",
    }
    _OPTIONAL_OBJECT_SECTIONS: ClassVar[set[str]] = {
        "constitution",
        "policy",
        "constraints",
        "runtime",
        "provenance",
    }

    def __init__(self, schema_path: Path | None = None) -> None:
        self.schema_path: Path = schema_path or self._default_schema_path()
        self.schema: dict[str, Any] = self._load_schema()

    def _default_schema_path(self) -> Path:
        if hasattr(settings.paths, "context_schema_path"):
            return settings.paths.context_schema_path()
        return settings.REPO_PATH / "var" / "context" / "schema.yaml"

    def _load_schema(self) -> dict[str, Any]:
        if not self.schema_path.exists():
            raise FileNotFoundError(f"Schema not found: {self.schema_path}")

        try:
            content = self.schema_path.read_text(encoding="utf-8")
            data = yaml.safe_load(content) or {}
        except Exception as exc:
            raise RuntimeError(
                f"Failed to load schema: {self.schema_path} ({exc})"
            ) from exc

        if not isinstance(data, dict):
            raise ValueError(
                f"Invalid schema format (expected mapping): {self.schema_path}"
            )

        return data

    # ID: decfe9e4-f915-4bcc-9ba0-46ea5bc713d7
    def validate(self, packet: dict[str, Any]) -> ValidationResult:
        errors: list[str] = []

        required_fields = self.schema.get("required_fields", [])
        if isinstance(required_fields, list):
            for field in required_fields:
                if field not in packet:
                    errors.append(f"Missing required field: {field}")

        errors.extend(self._validate_header(packet.get("header", {})))
        errors.extend(self._validate_phase(packet.get("phase")))
        errors.extend(self._validate_evidence(packet.get("evidence", [])))
        errors.extend(self._validate_optional_sections(packet))
        errors.extend(self._validate_constraints(packet.get("constraints", {})))
        errors.extend(self._validate_policy(packet))
        errors.extend(self._validate_provenance(packet.get("provenance", {})))

        header = packet.get("header")
        packet_id = (
            header.get("packet_id", "unknown")
            if isinstance(header, dict)
            else "unknown"
        )

        is_valid = not errors
        if is_valid:
            logger.info("Context packet validated: %s", packet_id)
        else:
            logger.warning(
                "Context validation failed (%s errors) for %s",
                len(errors),
                packet_id,
            )

        return ValidationResult(
            ok=is_valid,
            errors=errors,
            validated_data=packet if is_valid else {},
            metadata={"packet_id": packet_id},
        )

    def _validate_header(self, header: Any) -> list[str]:
        if not isinstance(header, dict):
            return ["Header must be an object"]

        errors: list[str] = []

        missing_fields = sorted(self._REQUIRED_HEADER_FIELDS - set(header.keys()))
        for field in missing_fields:
            errors.append(f"Header missing required field: {field}")

        privacy = header.get("privacy")
        if privacy is not None and privacy not in self._ALLOWED_PRIVACY_VALUES:
            errors.append(f"Invalid privacy value: {privacy}")

        return errors

    def _validate_phase(self, phase: Any) -> list[str]:
        if not isinstance(phase, str):
            return ["Phase must be a string"]
        if phase not in self._ALLOWED_PHASE_VALUES:
            return [f"Invalid phase value: {phase}"]
        return []

    def _validate_constraints(self, constraints: Any) -> list[str]:
        if not isinstance(constraints, dict):
            return ["Constraints must be an object"]

        errors: list[str] = []

        applicable_rules = constraints.get("applicable_rules")
        if applicable_rules is not None and not isinstance(applicable_rules, list):
            errors.append("Constraints.applicable_rules must be an array")

        return errors

    def _validate_evidence(self, evidence: Any) -> list[str]:
        if not isinstance(evidence, list):
            return ["Evidence must be an array"]

        errors: list[str] = []

        for idx, item in enumerate(evidence):
            if not isinstance(item, dict):
                errors.append(f"Evidence[{idx}] must be an object")
                continue

            missing_fields = sorted({"name", "item_type", "source"} - set(item.keys()))
            for field in missing_fields:
                errors.append(f"Evidence[{idx}] missing required field: {field}")

            item_type = item.get("item_type")
            if item_type is not None and item_type not in self._ALLOWED_ITEM_TYPES:
                errors.append(f"Evidence[{idx}] invalid item_type: {item_type}")

        return errors

    def _validate_optional_sections(self, packet: dict[str, Any]) -> list[str]:
        errors: list[str] = []

        for section in self._OPTIONAL_OBJECT_SECTIONS:
            if section in packet and not isinstance(packet[section], dict):
                errors.append(f"{section.capitalize()} must be an object")

        constitution = packet.get("constitution")
        if constitution is not None and not isinstance(constitution, dict):
            errors.append("Constitution must be an object")

        return errors

    def _validate_policy(self, packet: dict[str, Any]) -> list[str]:
        policy = packet.get("policy", {})
        header = packet.get("header", {})

        if not isinstance(policy, dict):
            return ["Policy must be an object"]
        if not isinstance(header, dict):
            return ["Header must be an object"]

        errors: list[str] = []

        privacy = header.get("privacy")
        remote_allowed = bool(policy.get("remote_allowed"))

        if privacy == "local_only" and remote_allowed:
            errors.append("Privacy is local_only but policy.remote_allowed is true")

        return errors

    def _validate_provenance(self, provenance: Any) -> list[str]:
        if not isinstance(provenance, dict):
            return ["Provenance must be an object"]

        errors: list[str] = []

        if "cache_key" in provenance and not isinstance(provenance["cache_key"], str):
            errors.append("Provenance.cache_key must be a string")

        if "providers" in provenance and not isinstance(provenance["providers"], list):
            errors.append("Provenance.providers must be an array")

        if "build_stats" in provenance and not isinstance(
            provenance["build_stats"], dict
        ):
            errors.append("Provenance.build_stats must be an object")

        return errors
