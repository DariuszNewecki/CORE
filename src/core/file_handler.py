# src/core/file_handler.py
"""
Backend File Handling Module (Refactored)

Handles staging and writing file changes. It supports traceable, auditable
operations. All writes go through a pending stage to enable review and rollback.
"""

import json
import threading
from datetime import datetime, timezone
from uuid import uuid4
from pathlib import Path
from typing import Dict, Optional, Any
from shared.logger import getLogger

# --- Global Setup ---
log = getLogger(__name__)
LOG_DIR = Path("logs")
PENDING_DIR = Path("pending_writes")
UNDO_LOG = LOG_DIR / "undo_log.jsonl"
pending_writes_storage: Dict[str, Dict[str, Any]] = {}
_storage_lock = threading.Lock()

# Ensure directories exist
LOG_DIR.mkdir(exist_ok=True)
PENDING_DIR.mkdir(exist_ok=True)


# --- FileHandler Class ---
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
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        with _storage_lock:
            pending_writes_storage[pending_id] = entry

        pending_file = PENDING_DIR / f"{pending_id}.json"
        pending_file.write_text(json.dumps(entry, indent=2), encoding="utf-8")
        return pending_id

    def confirm_write(self, pending_id: str) -> Dict[str, str]:
        """
        Confirms and applies a pending write to disk. Assumes content has been validated.
        """
        with _storage_lock:
            pending_op = pending_writes_storage.pop(pending_id, None)

        pending_file = PENDING_DIR / f"{pending_id}.json"
        if pending_file.exists():
            pending_file.unlink(missing_ok=True)

        if not pending_op:
            return {"status": "error", "message": f"Pending write ID '{pending_id}' not found or already processed."}

        file_rel_path = pending_op["path"]
        
        try:
            abs_file_path = self.repo_path / file_rel_path
            
            if not abs_file_path.resolve().is_relative_to(self.repo_path.resolve()):
                 raise ValueError(f"Attempted to write outside of repository boundary: {file_rel_path}")

            abs_file_path.parent.mkdir(parents=True, exist_ok=True)
            abs_file_path.write_text(pending_op["code"], encoding="utf-8")
            
            log.info(f"Wrote to {file_rel_path}")
            return {
                "status": "success",
                "message": f"Wrote to {file_rel_path}",
                "file_path": file_rel_path
            }
        except Exception as e:
            # If write fails, restore the pending operation for potential retry
            if pending_op:
                with _storage_lock:
                    pending_writes_storage[pending_id] = pending_op
                pending_file.write_text(json.dumps(pending_op, indent=2), encoding="utf-8")
            return {"status": "error", "message": f"Failed to write file: {str(e)}"}