# src/shared/infrastructure/storage/file_handler.py

"""
Provides safe, auditable file operations with staged writes
requiring confirmation for traceability and rollback capabilities.
"""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 6b734568-de0d-41d9-906e-aead976a4884
class FileHandler:
    """
    Central class for safe, auditable file operations in CORE.
    All writes are staged first and require confirmation. Validation is handled
    by the calling agent via the validation_pipeline.
    """

    def __init__(self, repo_path: str):
        """
        Initialize FileHandler with repository root.
        """
        self.repo_path = Path(repo_path).resolve()
        if not self.repo_path.is_dir():
            raise ValueError(f"Invalid repository path provided: {repo_path}")
        self.log_dir = self.repo_path / "logs"
        self.pending_dir = self.repo_path / "pending_writes"
        self.undo_log = self.log_dir / "undo_log.jsonl"
        self.log_dir.mkdir(exist_ok=True)
        self.pending_dir.mkdir(exist_ok=True)
        self.pending_writes: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    # ID: 5d05f5eb-0128-4117-8b2b-3c6334c841ab
    def add_pending_write(self, prompt: str, suggested_path: str, code: str) -> str:
        """
        Stages a pending write operation for later confirmation.
        """
        pending_id = str(uuid4())
        rel_path = Path(suggested_path).as_posix()
        entry = {
            "id": pending_id,
            "prompt": prompt,
            "path": rel_path,
            "code": code,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        with self._lock:
            self.pending_writes[pending_id] = entry
        pending_file = self.pending_dir / f"{pending_id}.json"
        pending_file.write_text(json.dumps(entry, indent=2), encoding="utf-8")
        return pending_id

    # ID: 3673a03c-38b9-4d58-9f24-df264841e0e9
    def confirm_write(self, pending_id: str) -> dict[str, str]:
        """
        Confirms and applies a pending write to disk. Assumes content has been validated.
        """
        with self._lock:
            pending_op = self.pending_writes.pop(pending_id, None)
        pending_file = self.pending_dir / f"{pending_id}.json"
        if pending_file.exists():
            pending_file.unlink(missing_ok=True)
        if not pending_op:
            return {
                "status": "error",
                "message": f"Pending write ID '{pending_id}' not found or already processed.",
            }
        file_rel_path = pending_op["path"]
        try:
            abs_file_path = self.repo_path / file_rel_path
            if not abs_file_path.resolve().is_relative_to(self.repo_path.resolve()):
                raise ValueError(
                    f"Attempted to write outside of repository boundary: {file_rel_path}"
                )
            abs_file_path.parent.mkdir(parents=True, exist_ok=True)
            abs_file_path.write_text(pending_op["code"], encoding="utf-8")
            logger.info("Wrote to %s", file_rel_path)
            return {
                "status": "success",
                "message": f"Wrote to {file_rel_path}",
                "file_path": file_rel_path,
            }
        except Exception as e:
            if pending_op:
                with self._lock:
                    self.pending_writes[pending_id] = pending_op
                pending_file.write_text(
                    json.dumps(pending_op, indent=2), encoding="utf-8"
                )
            return {"status": "error", "message": f"Failed to write file: {str(e)}"}
