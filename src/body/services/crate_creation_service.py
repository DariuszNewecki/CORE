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


# ID: b9ee3781-7db1-4445-a5f6-19eb7d658315
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
        self.crate_schema = settings.load(
            "charter.schemas.constitutional.intent_crate_schema"
        )
        logger.info("CrateCreationService initialized.")

    # ID: 0d490d0f-ab25-4c49-9bad-a9691a5f9448
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
                crate_id=crate_id,
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
                "Successfully created crate '%s' with %s files",
                crate_id,
                len(payload_files),
            )
            return crate_id
        except Exception as e:
            if crate_path.exists():
                import shutil

                shutil.rmtree(crate_path, ignore_errors=True)
            logger.error("Failed to create crate: %s", e, exc_info=True)
            action_logger.log_event(
                "crate.creation.failed", {"intent": intent, "error": str(e)}
            )
            raise

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

    def _create_manifest(
        self,
        crate_id: str,
        intent: str,
        payload_files: list[str],
        crate_type: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        manifest = {
            "crate_id": crate_id,
            "author": "CoderAgent",
            "intent": intent,
            "type": "CODE_MODIFICATION",
            "created_at": datetime.now(UTC).isoformat(),
            "generator": "CoderAgent",
            "generator_version": "0.2.0",
            "payload_files": payload_files,
            "metadata": metadata,
        }
        if crate_type == "STANDARD":
            manifest["type"] = "CODE_MODIFICATION"
        elif crate_type == "CONSTITUTIONAL_AMENDMENT":
            manifest["type"] = "CONSTITUTIONAL_AMENDMENT"
        strict_manifest = {
            "crate_id": manifest["crate_id"],
            "author": manifest["author"],
            "intent": manifest["intent"],
            "type": manifest["type"],
            "payload_files": manifest["payload_files"],
        }
        jsonschema.validate(instance=strict_manifest, schema=self.crate_schema)
        return strict_manifest

    def _write_payload_files(
        self, crate_path: Path, payload_files: dict[str, str]
    ) -> None:
        for relative_path, content in payload_files.items():
            file_path = crate_path / relative_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            logger.debug("Wrote payload file: %s", relative_path)

    # ID: cee36a3f-693c-4326-9ecd-1101d9c92bf3
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

    # ID: fc7dcb63-c6db-40db-b28d-e0f1518f4208
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


# ID: a5091f6d-4fb1-47d1-9769-3d59d82db735
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
