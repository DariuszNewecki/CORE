# src/shared/infrastructure/storage/integrity_service.py
# ID: 174a817b-2d3e-4f5c-8b2c-3d4e5f6a7b8c

"""
Integrity Service - Phase 2 Hardening.
Provides deterministic checksum verification for the codebase.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from shared.logger import getLogger
from shared.models.validation_result import ValidationResult


logger = getLogger(__name__)


# ID: 3e5c78c1-db6a-4ff8-8cdd-0f284b0acd80
class IntegrityService:
    """
    Manages codebase fingerprints to ensure deterministic state.
    """

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.integrity_dir = repo_root / "var" / "integrity"
        self.integrity_dir.mkdir(parents=True, exist_ok=True)

    # ID: ef8581d2-86f8-47f5-b1b8-27fb72b95b80
    def create_baseline(self, label: str = "default") -> Path:
        """
        Scans src/ and creates a signed baseline of all file hashes.
        """
        logger.info("Creating integrity baseline: %s", label)

        manifest = {
            "metadata": {
                "label": label,
                "timestamp": datetime.now(UTC).isoformat(),
                "repo_root": str(self.repo_root),
            },
            "files": self._hash_codebase(),
        }

        output_path = self.integrity_dir / f"baseline_{label}.json"
        output_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        logger.info("✅ Baseline saved to %s", output_path)
        return output_path

    # ID: 2cfcf898-5206-4247-bc6a-24042c430284
    def verify_integrity(self, label: str = "default") -> ValidationResult:
        """
        Compares current codebase against a saved baseline.
        """
        baseline_path = self.integrity_dir / f"baseline_{label}.json"
        if not baseline_path.exists():
            return ValidationResult(ok=False, errors=[f"Baseline '{label}' not found."])

        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        current_state = self._hash_codebase()

        errors = []
        # Check for modified or deleted files
        for path, expected_hash in baseline["files"].items():
            if path not in current_state:
                errors.append(f"DELETED: {path}")
            elif current_state[path] != expected_hash:
                errors.append(f"MODIFIED: {path}")

        # Check for new files
        for path in current_state:
            if path not in baseline["files"]:
                errors.append(f"NEW FILE: {path}")

        is_ok = len(errors) == 0
        return ValidationResult(
            ok=is_ok,
            errors=errors,
            metadata={"checked_at": datetime.now(UTC).isoformat()},
        )

    def _hash_codebase(self) -> dict[str, str]:
        """Calculates SHA256 for every file in src/."""
        hashes = {}
        src_path = self.repo_root / "src"

        for file_path in src_path.rglob("*.py"):
            if "__pycache__" in str(file_path):
                continue

            rel_path = str(file_path.relative_to(self.repo_root))
            hashes[rel_path] = self._generate_file_hash(file_path)

        return hashes

    @staticmethod
    def _generate_file_hash(path: Path) -> str:
        """Helper to generate a stable file hash."""
        sha256_hash = hashlib.sha256()
        with open(path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
