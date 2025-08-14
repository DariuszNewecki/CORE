# src/system/tools/change_log_updater.py

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from shared.config_loader import load_config
from shared.logger import getLogger

log = getLogger(__name__)

CHANGE_LOG_PATH = Path(".intent/knowledge/meta_code_change_log.json")
SCHEMA_VERSION = "1.0.0"


def load_existing_log() -> Dict:
    """Loads the existing change log from disk or returns a new structure."""
    data = load_config(CHANGE_LOG_PATH, "json")
    if not data:
        return {"schema_version": SCHEMA_VERSION, "changes": []}
    return data


def append_change_entry(
    task: str,
    step: str,
    modified_files: List[str],
    score: float,
    violations: List[Dict],
):
    """Appends a new, structured entry to the metacode change log."""
    log_data = load_existing_log()
    timestamp = datetime.utcnow().isoformat() + "Z"

    log_data["changes"].append(
        {
            "timestamp": timestamp,
            "task": task,
            "step": step,
            "modified_files": modified_files,
            "score": score,
            "violations": violations,
            "source": "orchestrator",
        }
    )

    CHANGE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHANGE_LOG_PATH.write_text(json.dumps(log_data, indent=2), encoding="utf-8")
    log.info(f"Appended change log entry at {timestamp}.")


if __name__ == "__main__":
    # Example usage for testing
    append_change_entry(
        task="Add intent guard integration",
        step="Check manifest before file write",
        modified_files=["src/core/cli.py", "src/core/intent_guard.py"],
        score=0.85,
        violations=[],
    )
