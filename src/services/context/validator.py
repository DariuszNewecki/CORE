# src/services/context/validator.py

"""ContextValidator - Enforces schema.yaml compliance.

Validates packets against .intent/context/schema.yaml.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml


logger = logging.getLogger(__name__)


# ID: ee2b8825-e015-4742-833e-ea0afb973045
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

    # ID: 94683d64-c686-4618-a6ff-de6224471a88
    def validate(self, packet: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate packet against schema.

        Args:
            packet: ContextPackage dict

        Returns:
            Tuple of (is_valid, errors)
        """
        errors = []

        # Check version
        if not self._check_version(packet):
            errors.append("Schema version mismatch or missing")

        # Check required top-level fields
        required = self.schema.get("required_fields", [])
        for field in required:
            if field not in packet:
                errors.append(f"Missing required field: {field}")

        # Validate header
        header_errors = self._validate_header(packet.get("header", {}))
        errors.extend(header_errors)

        # Validate constraints
        constraint_errors = self._validate_constraints(packet)
        errors.extend(constraint_errors)

        # Validate context array
        context_errors = self._validate_context(packet.get("context", []))
        errors.extend(context_errors)

        # Validate policy
        policy_errors = self._validate_policy(packet)
        errors.extend(policy_errors)

        is_valid = len(errors) == 0
        if is_valid:
            logger.info(f"Packet {packet.get('header', {}).get('packet_id')} validated")
        else:
            logger.warning(f"Validation failed: {len(errors)} errors")

        return is_valid, errors

    def _check_version(self, packet: dict[str, Any]) -> bool:
        """Check schema version compatibility."""
        # TODO: Implement version checking
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

        # Privacy enum check
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

        # Token budget check
        if "max_tokens" in constraints:
            total_tokens = sum(
                item.get("tokens_est", 0) for item in packet.get("context", [])
            )
            if total_tokens > constraints["max_tokens"]:
                errors.append(
                    f"Token budget exceeded: {total_tokens} > {constraints['max_tokens']}"
                )

        # Item limit check
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

            # Check item_type enum
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

        # Check privacy/remote_allowed consistency
        privacy = header.get("privacy")
        remote_allowed = policy.get("remote_allowed")

        if privacy == "local_only" and remote_allowed:
            errors.append("Privacy is local_only but remote_allowed is true")

        if privacy == "remote_allowed" and not remote_allowed:
            errors.append("Privacy is remote_allowed but remote_allowed is false")

        return errors
