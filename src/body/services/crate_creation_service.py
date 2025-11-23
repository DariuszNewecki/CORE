# ID: a32fda64-02db-486b-9b40-a3d5f2410107
# ID: 756b601e-01e5-4990-8946-7eb490464eec
# ID: crate.create.from_generation
# ID: crate.create.from_generation
# ID: crate.create.from_generation
# ID: crate.create.from_generation
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
            logger.info(f"Created crate directory: {crate_id}")

            manifest = self._create_manifest(
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
        intent: str,
        payload_files: list[str],
        crate_type: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        manifest = {
            "intent": intent,
            "type": crate_type,
            "created_at": datetime.now(UTC).isoformat(),
            "generator": "CoderAgent",
            "generator_version": "0.2.0",
            "payload_files": payload_files,
            "metadata": metadata,
        }

        jsonschema.validate(instance=manifest, schema=self.crate_schema)
        return manifest

    # ID: 4f8d2c1b-3e5a-6789-bcd0-123456789abc
    def _write_payload_files(
        self, crate_path: Path, payload_files: dict[str, str]
    ) -> None:
        for relative_path, content in payload_files.items():
            file_path = crate_path / relative_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            logger.debug(f"Wrote payload file: {relative_path}")

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
# ID: da76c9d7-22c3-40fa-9b64-fff3cee92e42
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
