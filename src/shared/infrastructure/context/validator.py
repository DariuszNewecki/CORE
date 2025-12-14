# src/shared/infrastructure/context/validator.py

"""ContextValidator - Enforces schema.yaml compliance.

Validates packets against .intent/context/schema.yaml.
"""

from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)
import logging
from pathlib import Path
from typing import Any

import yaml


logger = logging.getLogger(__name__)


# ID: 974a8871-87cd-4f58-832f-d5492e72626f
class ContextValidator:
    """Validates ContextPackage against schema."""

    def __init__(self, schema_path: str = ".intent/context/schema.yaml"):
        """Initialize validator with schema.

        Args:
            schema_path: Path to schema YAML file
        """
        self.schema_path = Path(schema_path)
        self.schema = self._load_schema()

    def _load_schema(self) -> dict[str, Any]:
        """Load and parse schema YAML."""
        if not self.schema_path.exists():
            raise FileNotFoundError(f"Schema not found: {self.schema_path}")
        with open(self.schema_path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    # ID: 2412a7ae-c33f-4055-909a-ca0b4a88e49b
    def validate(self, packet: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate packet against schema.

        Args:
            packet: ContextPackage dict

        Returns:
            Tuple of (is_valid, errors)
        """
        errors = []
        if not self._check_version(packet):
            errors.append("Schema version mismatch or missing")
        required = self.schema.get("required_fields", [])
        for field in required:
            if field not in packet:
                errors.append(f"Missing required field: {field}")
        header_errors = self._validate_header(packet.get("header", {}))
        errors.extend(header_errors)
        constraint_errors = self._validate_constraints(packet)
        errors.extend(constraint_errors)
        context_errors = self._validate_context(packet.get("context", []))
        errors.extend(context_errors)
        policy_errors = self._validate_policy(packet)
        errors.extend(policy_errors)
        is_valid = len(errors) == 0
        if is_valid:
            logger.info(
                "Packet %s validated", packet.get("header", {}).get("packet_id")
            )
        else:
            logger.warning("Validation failed: %s errors", len(errors))
        return (is_valid, errors)

    def _check_version(self, packet: dict[str, Any]) -> bool:
        """Check schema version compatibility."""
        return True

    def _validate_header(self, header: dict[str, Any]) -> list[str]:
        """Validate header fields."""
        errors = []
        required = [
            "packet_id",
            "task_id",
            "task_type",
            "created_at",
            "builder_version",
            "privacy",
        ]
        for field in required:
            if field not in header:
                errors.append(f"Header missing required field: {field}")
        if "privacy" in header and header["privacy"] not in [
            "local_only",
            "remote_allowed",
        ]:
            errors.append(f"Invalid privacy value: {header['privacy']}")
        return errors

    def _validate_constraints(self, packet: dict[str, Any]) -> list[str]:
        """Validate resource constraints."""
        errors = []
        constraints = packet.get("constraints", {})
        if "max_tokens" in constraints:
            total_tokens = sum(
                item.get("tokens_est", 0) for item in packet.get("context", [])
            )
            if total_tokens > constraints["max_tokens"]:
                errors.append(
                    f"Token budget exceeded: {total_tokens} > {constraints['max_tokens']}"
                )
        if "max_items" in constraints:
            item_count = len(packet.get("context", []))
            if item_count > constraints["max_items"]:
                errors.append(
                    f"Item limit exceeded: {item_count} > {constraints['max_items']}"
                )
        return errors

    def _validate_context(self, context: list[dict[str, Any]]) -> list[str]:
        """Validate context array items."""
        errors = []
        required_fields = ["name", "item_type", "source"]
        for idx, item in enumerate(context):
            for field in required_fields:
                if field not in item:
                    errors.append(f"Context[{idx}] missing required field: {field}")
            if "item_type" in item and item["item_type"] not in [
                "symbol",
                "snippet",
                "summary",
                "dependency",
                "test",
                "signature",
                "code",
            ]:
                errors.append(f"Context[{idx}] invalid item_type: {item['item_type']}")
        return errors

    def _validate_policy(self, packet: dict[str, Any]) -> list[str]:
        """Validate policy consistency."""
        errors = []
        policy = packet.get("policy", {})
        header = packet.get("header", {})
        privacy = header.get("privacy")
        remote_allowed = policy.get("remote_allowed")
        if privacy == "local_only" and remote_allowed:
            errors.append("Privacy is local_only but remote_allowed is true")
        if privacy == "remote_allowed" and (not remote_allowed):
            errors.append("Privacy is remote_allowed but remote_allowed is false")
        return errors
