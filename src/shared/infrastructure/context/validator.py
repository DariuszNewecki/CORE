# src/shared/infrastructure/context/validator.py

"""
ContextValidator - Enforces ContextPackage schema compliance.

Validates packets against the runtime schema stored under:
    var/context/schema.yaml
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

import yaml

from shared.config import settings
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 974a8871-87cd-4f58-832f-d5492e72626f
class ContextValidator:
    """Validates ContextPackage packets against the runtime schema."""

    _REQUIRED_HEADER_FIELDS: ClassVar[set[str]] = {
        "packet_id",
        "task_id",
        "task_type",
        "created_at",
        "builder_version",
        "privacy",
    }

    _ALLOWED_PRIVACY_VALUES: ClassVar[set[str]] = {"local_only", "remote_allowed"}

    _ALLOWED_ITEM_TYPES: ClassVar[set[str]] = {
        "symbol",
        "snippet",
        "summary",
        "dependency",
        "test",
        "signature",
        "code",
    }

    def __init__(self, schema_path: Path | None = None):
        """
        Initialize validator with schema.

        Args:
            schema_path: Optional override path to schema YAML.
                         Defaults to var/context/schema.yaml via settings.
        """
        self.schema_path: Path = schema_path or self._default_schema_path()
        self.schema: dict[str, Any] = self._load_schema()

    def _default_schema_path(self) -> Path:
        """Resolve the default schema path."""
        if hasattr(settings.paths, "context_schema_path"):
            return settings.paths.context_schema_path()  # type: ignore[attr-defined]
        return settings.REPO_PATH / "var" / "context" / "schema.yaml"

    def _load_schema(self) -> dict[str, Any]:
        """Load and parse schema YAML."""
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

    def _safe_int(self, value: Any) -> int:
        """Best-effort integer conversion (returns 0 on bad input)."""
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    # ID: 2412a7ae-c33f-4055-909a-ca0b4a88e49b
    def validate(self, packet: dict[str, Any]) -> tuple[bool, list[str]]:
        """
        Validate packet against schema.

        Args:
            packet: ContextPackage dict

        Returns:
            Tuple of (is_valid, errors)
        """
        errors: list[str] = []

        # Version check (currently permissive)
        if not self._check_version(packet):
            errors.append("Schema version mismatch or missing")

        # Required fields from schema
        required_fields = self.schema.get("required_fields", [])
        if isinstance(required_fields, list):
            for field in required_fields:
                if field not in packet:
                    errors.append(f"Missing required field: {field}")

        # Validate components
        errors.extend(self._validate_header(packet.get("header", {})))
        errors.extend(self._validate_constraints(packet))
        errors.extend(self._validate_context(packet.get("context", [])))
        errors.extend(self._validate_policy(packet))

        # Log results (type-safe packet_id extraction)
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

        return (is_valid, errors)

    def _check_version(self, packet: dict[str, Any]) -> bool:
        """Check schema version compatibility (currently permissive)."""
        return True

    def _validate_header(self, header: dict[str, Any]) -> list[str]:
        """Validate header fields."""
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

    def _validate_constraints(self, packet: dict[str, Any]) -> list[str]:
        """Validate resource constraints."""
        constraints = packet.get("constraints", {})
        if not isinstance(constraints, dict):
            return ["Constraints must be an object"]

        errors: list[str] = []
        context_items = packet.get("context", [])

        # Validate max_tokens
        if "max_tokens" in constraints:
            try:
                max_tokens = int(constraints["max_tokens"])
            except (ValueError, TypeError):
                return ["constraints.max_tokens must be an integer"]

            if isinstance(context_items, list):
                total_tokens = sum(
                    self._safe_int(item.get("tokens_est", 0))
                    for item in context_items
                    if isinstance(item, dict)
                )
                if total_tokens > max_tokens:
                    errors.append(
                        f"Token budget exceeded: {total_tokens} > {max_tokens}"
                    )

        # Validate max_items
        if "max_items" in constraints:
            try:
                max_items = int(constraints["max_items"])
            except (ValueError, TypeError):
                return ["constraints.max_items must be an integer"]

            if isinstance(context_items, list) and len(context_items) > max_items:
                errors.append(
                    f"Item limit exceeded: {len(context_items)} > {max_items}"
                )

        return errors

    def _validate_context(self, context: Any) -> list[str]:
        """Validate context array items."""
        if not isinstance(context, list):
            return ["Context must be an array"]

        errors: list[str] = []

        for idx, item in enumerate(context):
            if not isinstance(item, dict):
                errors.append(f"Context[{idx}] must be an object")
                continue

            missing_fields = sorted({"name", "item_type", "source"} - set(item.keys()))
            for field in missing_fields:
                errors.append(f"Context[{idx}] missing required field: {field}")

            item_type = item.get("item_type")
            if item_type is not None and item_type not in self._ALLOWED_ITEM_TYPES:
                errors.append(f"Context[{idx}] invalid item_type: {item_type}")

        return errors

    def _validate_policy(self, packet: dict[str, Any]) -> list[str]:
        """Validate policy consistency."""
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
        elif privacy == "remote_allowed" and not remote_allowed:
            errors.append(
                "Privacy is remote_allowed but policy.remote_allowed is false"
            )

        return errors
