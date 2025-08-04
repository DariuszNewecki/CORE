# src/core/file_handler.py
"""
Backend File Handling Module (Refactored)

Handles staging, writing, validating, and undoing file changes.
Integrates with safety policies and supports traceable, auditable operations.
All writes go through a pending stage to enable review and rollback.
"""

import json
import threading
from datetime import datetime, timezone
from uuid import uuid4
from pathlib import Path
from typing import Dict, Optional, Any

# Import from shared utilities
#from shared.path_utils import 
from shared.config_loader import load_config


# --- Constants ---
LOG_DIR = Path("logs")
PENDING_DIR = Path("pending_writes")
CHANGE_LOG_PATH = Path(".intent/change_log.json")
SAFETY_POLICIES_PATH = Path(".intent/policies/safety_policies.yaml")
UNDO_LOG = LOG_DIR / "undo_log.jsonl"


# --- Global State & Setup ---
pending_writes_storage: Dict[str, Dict[str, Any]] = {}
_storage_lock = threading.Lock()

# Ensure directories exist
LOG_DIR.mkdir(exist_ok=True)
PENDING_DIR.mkdir(exist_ok=True)


# --- Logging ---
# def log_action(action_type: str, data: dict):
#     """
#     Logs an action to the central actions.log for auditability.
#     """
#     try:
#         log_entry = {
#             "timestamp": datetime.now(timezone.utc).isoformat(),
#             "action": action_type,
#             **data
#         }
#         with open(LOG_DIR / "actions.log", "a", encoding="utf-8") as f:
#             f.write(json.dumps(log_entry) + "\n")
#     except Exception as e:
#         print(f"⚠️ Failed to log action: {str(e)}")


# --- Change Log ---
def _log_change(file_path: str, reason: str):
    """
    Appends a change entry to the intent change log.
    """
    change_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "file": file_path,
        "reason": reason,
    }
    
    try:
        if CHANGE_LOG_PATH.exists():
            change_log = json.loads(CHANGE_LOG_PATH.read_text(encoding="utf-8"))
        else:
            change_log = {"schema_version": "1.0", "changes": []}
        
        change_log["changes"].append(change_entry)
        
        CHANGE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CHANGE_LOG_PATH.write_text(json.dumps(change_log, indent=2), encoding="utf-8")
        print(f"✅ Logged change for {file_path}")
    except Exception as e:
        print(f"❌ Error logging change for {file_path}: {e}")


# --- Validation ---
def _validate_content(content: str, file_path: str) -> bool:
    """
    Validates content against safety policies (e.g., no eval, subprocess, etc.).
    """
    safety_policies = load_config(SAFETY_POLICIES_PATH, "yaml")
    if not safety_policies:
        return True # If no policies, assume content is safe.
        
    forbidden_calls = []
    for rule in safety_policies.get("rules", []):
        if rule.get("id") == "no_dangerous_execution":
            patterns = rule.get("detection", {}).get("patterns", [])
            forbidden_calls.extend(patterns)

    for forbidden in forbidden_calls:
        if forbidden in content:
            print(f"❌ Validation failed: Dangerous pattern '{forbidden}' detected in {file_path}")
            return False
    return True


# --- FileHandler Class ---
class FileHandler:
    """
    Central class for safe, auditable file operations in CORE.
    All writes are staged first and require confirmation.
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
        Confirms and applies a pending write to disk.
        """
        with _storage_lock:
            pending_op = pending_writes_storage.pop(pending_id, None)

        pending_file = PENDING_DIR / f"{pending_id}.json"
        if pending_file.exists():
            pending_file.unlink()

        if not pending_op:
            return {"status": "error", "message": f"Pending write ID '{pending_id}' not found or already processed."}

        file_rel_path = pending_op["path"]
        
        if not _validate_content(pending_op["code"], file_rel_path):
            return {"status": "error", "message": f"Validation failed for {file_rel_path}"}

        try:
            abs_file_path = self.repo_path / file_rel_path
            
            if not abs_file_path.resolve().is_relative_to(self.repo_path.resolve()):
                 raise ValueError(f"Attempted to write outside of repository boundary: {file_rel_path}")

            abs_file_path.parent.mkdir(parents=True, exist_ok=True)
            abs_file_path.write_text(pending_op["code"], encoding="utf-8")
            
            _log_change(file_rel_path, pending_op["prompt"])
            return {
                "status": "success",
                "message": f"Wrote to {file_rel_path}",
                "file_path": file_rel_path
            }
        except Exception as e:
            return {"status": "error", "message": f"Failed to write file: {str(e)}"}
