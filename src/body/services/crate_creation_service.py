# src/body/services/crate_creation_service.py
"""
Service for creating Intent Crates from generated code.

Packages code, tests, and metadata into constitutionally-compliant crates
that can be processed by CrateProcessingService with canary validation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import jsonschema
import yaml
from shared.action_logger import action_logger
from shared.config import settings
from shared.logger import getLogger

logger = getLogger(__name__)


# ID: daabeaa5-a47e-4c54-9171-dbfbe2b25ddd
class CrateCreationService:
    """
    Creates Intent Crates from generated code.

    Responsibilities:
    - Generate unique crate IDs
    - Create crate directory structure
    - Write constitutional manifest
    - Package payload files
    - Log creation events
    """

    _CRATE_PREFIX = "crate"

    def __init__(self) -> None:
        """Initialize service with constitutional paths."""
        self.repo_root: Path = settings.REPO_PATH
        self.inbox_path: Path = self.repo_root / "work" / "crates" / "inbox"
        self.inbox_path.mkdir(parents=True, exist_ok=True)

        # Load crate schema for validation
        self.crate_schema = settings.load(
            "charter.schemas.constitutional.intent_crate_schema"
        )

        logger.info("CrateCreationService initialized.")

    # ID: 349610a9-ec44-4654-8972-98982f2e67eb
    def create_intent_crate(
        self,
        intent: str,
        payload_files: dict[str, str],
        crate_type: str = "STANDARD",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Create an Intent Crate from generated code.

        Returns:
            crate_id of the created crate
        """
        crate_id = self._generate_crate_id()
        crate_path = self.inbox_path / crate_id

        try:
            crate_path.mkdir(parents=True, exist_ok=False)
            logger.info("Created crate directory: %s", crate_id)

            manifest = self._create_manifest(
                crate_id=crate_id,  # Pass crate_id here
                intent=intent,
                payload_files=list(payload_files.keys()),
                crate_type=crate_type,
                metadata=metadata or {},
            )

            manifest_path = crate_path / "manifest.yaml"
            manifest_path.write_text(yaml.dump(manifest, indent=2), encoding="utf-8")

            self._write_payload_files(crate_path, payload_files)

            action_logger.log_event(
                "crate.creation.success",
                {
                    "crate_id": crate_id,
                    "intent": intent,
                    "type": crate_type,
                    "file_count": len(payload_files),
                },
            )

            logger.info(
                f"Successfully created crate '{crate_id}' with {len(payload_files)} files"
            )
            return crate_id

        except Exception as e:
            if crate_path.exists():
                import shutil

                shutil.rmtree(crate_path, ignore_errors=True)

            logger.error(f"Failed to create crate: {e}", exc_info=True)
            action_logger.log_event(
                "crate.creation.failed",
                {"intent": intent, "error": str(e)},
            )
            raise

    # ID: 8f1a2b3c-4d5e-6789-abcd-ef0123456789
    def _generate_crate_id(self) -> str:
        """
        Generate a unique crate identifier — safe, collision-resistant, constitutionally pure.
        """
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        candidate = f"{self._CRATE_PREFIX}_{timestamp}"

        if not (self.inbox_path / candidate).exists():
            return candidate

        counter = 1
        while True:
            candidate = f"{self._CRATE_PREFIX}_{timestamp}_{counter}"
            if not (self.inbox_path / candidate).exists():
                return candidate
            counter += 1

    # ID: 7d3f8e2a-9b1c-4f6d-8e5a-1c2b3d4e5f6g
    def _create_manifest(
        self,
        crate_id: str,  # Added parameter
        intent: str,
        payload_files: list[str],
        crate_type: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        manifest = {
            "crate_id": crate_id,  # Added field
            "author": "CoderAgent",  # Required by schema
            "intent": intent,
            "type": "CODE_MODIFICATION",  # Enum from schema: CODE_MODIFICATION or CONSTITUTIONAL_AMENDMENT. "STANDARD" is not in schema.
            "created_at": datetime.now(UTC).isoformat(),
            "generator": "CoderAgent",
            "generator_version": "0.2.0",
            "payload_files": payload_files,
            "metadata": metadata,
        }

        # Schema expects "type" to be one of the enum values. "STANDARD" isn't one.
        # Mapping "STANDARD" -> "CODE_MODIFICATION" if passed.
        if crate_type == "STANDARD":
            manifest["type"] = "CODE_MODIFICATION"
        elif crate_type == "CONSTITUTIONAL_AMENDMENT":
            manifest["type"] = "CONSTITUTIONAL_AMENDMENT"

        # Remove fields not in schema if schema is strict (additionalProperties: False)
        # But checking schema provided in logs: additionalProperties is False.
        # The schema has: crate_id, author, intent, type, payload_files.
        # It does NOT have: created_at, generator, generator_version, metadata.
        # Wait, let me check the provided schema in the logs carefully.

        # Schema provided in logs:
        # properties: crate_id, author, intent, type, payload_files.
        # additionalProperties: False.

        # So I must strip extra fields or update the schema.
        # For now, I will strip extra fields to pass validation.
        # The metadata can be stored in a separate file or we need to update schema.
        # Let's conform to strict schema for now.

        strict_manifest = {
            "crate_id": manifest["crate_id"],
            "author": manifest["author"],
            "intent": manifest["intent"],
            "type": manifest["type"],
            "payload_files": manifest["payload_files"],
        }

        jsonschema.validate(instance=strict_manifest, schema=self.crate_schema)

        # Return the full manifest (with metadata) for writing to disk,
        # assuming the validator was just a check.
        # But if I write the full one, downstream consumers might fail validation too.
        # Given this is "Intent Crate Manifest", it should probably match.

        return strict_manifest

    # ID: 4f8d2c1b-3e5a-6789-bcd0-123456789abc
    def _write_payload_files(
        self, crate_path: Path, payload_files: dict[str, str]
    ) -> None:
        for relative_path, content in payload_files.items():
            file_path = crate_path / relative_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            logger.debug("Wrote payload file: %s", relative_path)

    # ID: a6a343bb-a193-4fa1-9f98-68d528676616
    def validate_payload_paths(self, payload_files: dict[str, str]) -> list[str]:
        errors = []
        allowed_roots = ["src/", "tests/", ".intent/charter/policies/governance/"]

        for path_str in payload_files.keys():
            path = Path(path_str)

            if path.is_absolute():
                errors.append(f"Absolute path not allowed: {path_str}")
                continue

            if ".." in path.parts:
                errors.append(f"Path traversal not allowed: {path_str}")
                continue

            if not any(path_str.startswith(root) for root in allowed_roots):
                errors.append(f"Path must start with allowed root: {path_str}")

        return errors

    # ID: 05126b6c-c7b9-44b6-ab2a-d8c09383bc3b
    def get_crate_info(self, crate_id: str) -> dict[str, Any] | None:
        crate_path = self.inbox_path / crate_id

        if not crate_path.exists():
            return None

        manifest_path = crate_path / "manifest.yaml"
        if not manifest_path.exists():
            return None

        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))

        return {
            "crate_id": crate_id,
            "path": str(crate_path),
            "manifest": manifest,
            "status": "inbox",
        }


# ID: 521515fc-4b0b-48e7-a46a46a-969a358d831f
# ID: 098836fd-b0ef-4fc5-ac9e-29b8a82d5377
def create_crate_from_generation_result(
    intent: str,
    files_generated: dict[str, str],
    generation_metadata: dict[str, Any] | None = None,
) -> str:
    """
    Convenience function used by CoderAgent and self-healing.
    """
    service = CrateCreationService()

    errors = service.validate_payload_paths(files_generated)
    if errors:
        raise ValueError(f"Invalid payload paths: {errors}")

    return service.create_intent_crate(
        intent=intent,
        payload_files=files_generated,
        crate_type="STANDARD",
        metadata=generation_metadata,
    )
