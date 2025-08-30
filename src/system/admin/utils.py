# src/system/admin/utils.py
"""
Intent: Shared admin utilities used by CLI commands. These helpers are small,
documented, and domain-aligned so they can be safely referenced by the auditor.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import yaml
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from shared.config import settings
from shared.logger import getLogger

log = getLogger("core_admin")


# CAPABILITY: governance.cli.should_fail
def should_fail(report: dict, fail_on: str) -> bool:
    """Determines if the CLI should exit with an error code based on the drift report and the specified fail condition (missing, undeclared, or any drift)."""
    if fail_on == "missing":
        return bool(report.get("missing_in_code"))
    if fail_on == "undeclared":
        return bool(report.get("undeclared_in_manifest"))
    return bool(
        report.get("missing_in_code")
        or report.get("undeclared_in_manifest")
        or report.get("mismatched_mappings")
    )


# CAPABILITY: governance.cli.load_yaml
def load_yaml_file(path: Path) -> Dict[str, Any]:
    """Intent: Load YAML for governance operations. Returns {} for empty documents."""
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


# CAPABILITY: governance.cli.save_yaml
def save_yaml_file(path: Path, data: Dict[str, Any]) -> None:
    """Intent: Persist YAML with stable ordering to ensure consistent hashes."""
    # Using sort_keys=True creates a canonical file format, which is essential for stable hashing.
    path.write_text(yaml.dump(data, sort_keys=True), encoding="utf-8")


def _get_canonical_payload(proposal: Dict[str, Any]) -> str:
    """
    Creates a stable, sorted JSON string of the proposal's core intent,
    ignoring all other metadata like signatures. This is the single source
    of truth for what gets signed.
    """
    signable_data = {
        "target_path": proposal.get("target_path"),
        "action": proposal.get("action"),
        "justification": proposal.get("justification"),
        "content": proposal.get("content", ""),
    }
    # Using json.dumps with sort_keys is the most reliable way to get a
    # canonical string representation of the data structure.
    return json.dumps(signable_data, sort_keys=True)


# CAPABILITY: governance.cli.generate_token
def generate_approval_token(proposal: Dict[str, Any]) -> str:
    """
    Intent: Produce a deterministic token based on a canonical representation
    of the proposal's intent.
    """
    canonical_string = _get_canonical_payload(proposal)
    digest = hashes.Hash(hashes.SHA256())
    digest.update(canonical_string.encode("utf-8"))

    # Version bump to reflect this definitive new token scheme.
    return f"core-proposal-v6:{digest.finalize().hex()}"


# CAPABILITY: governance.cli.load_key
def load_private_key() -> ed25519.Ed25519PrivateKey:
    """Intent: Load the operator's Ed25519 private key from the protected key store."""
    key_path = settings.MIND / "keys" / "private.key"
    if not key_path.exists():
        log.error(
            "❌ Private key not found. Please run 'core-admin keygen' to create one."
        )
        raise SystemExit(1)
    return serialization.load_pem_private_key(key_path.read_bytes(), password=None)


# --- THIS IS THE FIX ---
# We are adding the missing capability tag to the function.
# CAPABILITY: governance.cli.archive_plan
def archive_rollback_plan(proposal_name: str, proposal: Dict[str, Any]) -> None:
    # --- END OF FIX ---
    """Intent: Persist a rollback plan snapshot for approved proposals."""
    rollback_plan = proposal.get("rollback_plan")
    if not rollback_plan:
        return
    rollbacks_dir = settings.MIND / "constitution" / "rollbacks"
    rollbacks_dir.mkdir(parents=True, exist_ok=True)
    archive_path = (
        rollbacks_dir
        / f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{proposal_name}.json"
    )
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
