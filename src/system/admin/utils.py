# src/system/admin/utils.py
"""
Intent: Shared admin utilities used by CLI commands. These helpers are small,
documented, and domain-aligned so they can be safely referenced by the auditor.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import yaml
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from shared.config import settings
from shared.logger import getLogger

log = getLogger("core_admin")

# --- THIS IS THE NEW, SHARED FUNCTION ---
def should_fail(report: dict, fail_on: str) -> bool:
    """Determines if the CLI should exit with an error code based on the drift report and the specified fail condition (missing, undeclared, or any drift)."""
    """Determines if the CLI should exit with an error code based on the drift report."""
    if fail_on == "missing":
        return bool(report.get("missing_in_code"))
    if fail_on == "undeclared":
        return bool(report.get("undeclared_in_manifest"))
    # Default to 'any'
    return bool(report.get("missing_in_code") or report.get("undeclared_in_manifest") or report.get("mismatched_mappings"))
# --- END OF NEW FUNCTION ---

def load_yaml_file(path: Path) -> Dict[str, Any]:
    """Intent: Load YAML for governance operations. Returns {} for empty documents."""
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


    """Save the given data as a YAML file at the specified path without sorting keys for readability."""
def save_yaml_file(path: Path, data: Dict[str, Any]) -> None:
    """Intent: Persist YAML with stable ordering disabled to preserve human readability."""
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def generate_approval_token(proposal_content: str) -> str:
    """Intent: Produce a deterministic content-bound token for cryptographic proposal approvals."""
    digest = hashes.Hash(hashes.SHA256())
    digest.update((proposal_content or "").encode("utf-8"))
    return f"core-proposal-v1:{digest.finalize().hex()}"


def load_private_key() -> ed25519.Ed25519PrivateKey:
    """Intent: Load the operator's Ed25519 private key from the protected key store."""
    key_path = settings.KEY_STORAGE_DIR / "private.key"
    if not key_path.exists():
        log.error("❌ Private key not found. Please run 'core-admin keygen' to create one.")
        raise SystemExit(1)
    return serialization.load_pem_private_key(key_path.read_bytes(), password=None)

    """Persist a rollback plan snapshot for approved proposals under .intent/constitution/rollbacks/ as a timestamped JSON file."""

def archive_rollback_plan(proposal_name: str, proposal: Dict[str, Any]) -> None:
    """Intent: Persist a rollback plan snapshot for approved proposals under .intent/constitution/rollbacks/."""
    rollback_plan = proposal.get("rollback_plan")
    if not rollback_plan:
        return
    rollbacks_dir = settings.MIND / "constitution" / "rollbacks"
    rollbacks_dir.mkdir(parents=True, exist_ok=True)
    archive_path = rollbacks_dir / f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{proposal_name}.json"
    archive_path.write_text(
        json.dumps(
            {
                "proposal_name": proposal_name,
                "target_path": proposal.get("target_path"),
                "justification": proposal.get("justification"),
                "rollback_plan": rollback_plan,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    log.info(f"📖 Rollback plan archived to {archive_path}")