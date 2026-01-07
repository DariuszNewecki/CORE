# src/mind/governance/key_management_service.py

"""
Intent: Key management commands for the CORE Admin CLI.
Provides Ed25519 key generation and helper output for approver configuration.

CONSTITUTIONAL FIX:
- Aligned with 'governance.artifact_mutation.traceable'.
- Replaced direct Path writes with governed FileHandler mutations.
- Enforces IntentGuard and audit logging for security identity creation.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from shared.config import settings
from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger


logger = getLogger(__name__)
log = logger  # keep tests and tools happy


# ID: 2631affb-7466-4ee6-8907-397e60a4f220
class KeyManagementError(RuntimeError):
    """Raised when key management operations fail."""

    def __init__(self, message: str, *, exit_code: int = 1):
        super().__init__(message)
        self.exit_code = exit_code


# ID: f8491062-091f-49e6-acbf-9b3ee994409e
def keygen(
    identity: str,
    *,
    allow_overwrite: bool = False,
) -> None:
    """Intent: Generate a new Ed25519 key pair and print an approver YAML block."""
    logger.info("🔑 Generating new key pair for identity: %s", identity)

    # CONSTITUTIONAL FIX: Use the governed mutation surface
    fh = FileHandler(str(settings.REPO_PATH))

    # Resolve relative paths for FileHandler API
    try:
        rel_key_dir = str(settings.KEY_STORAGE_DIR.relative_to(settings.REPO_PATH))
    except ValueError:
        # Fallback if settings are absolute or unusual
        rel_key_dir = ".intent/keys"

    rel_private_key_path = f"{rel_key_dir}/private.key"
    abs_private_key_path = settings.REPO_PATH / rel_private_key_path

    if abs_private_key_path.exists():
        if not allow_overwrite:
            raise KeyManagementError(
                "A private key already exists. Use allow_overwrite to replace it.",
                exit_code=1,
            )

    # Generate the identity
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    pem_private = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    # Governed directory creation and write
    fh.ensure_dir(rel_key_dir)
    fh.write_runtime_bytes(rel_private_key_path, pem_private)

    # Ensure strict permissions on the resulting file
    if abs_private_key_path.exists():
        os.chmod(abs_private_key_path, 0o600)

    pem_public = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    logger.info(
        "\n✅ Private key saved securely via FileHandler to: %s", rel_private_key_path
    )
    logger.info(
        "\n📋 Add the following YAML block to '.intent/constitution/approvers.yaml' under 'approvers':\n"
    )

    approver_data = {
        "identity": identity,
        "public_key": pem_public.decode("utf-8"),
        "created_at": datetime.now(UTC).isoformat(),
        "role": "maintainer",
        "description": "Primary maintainer",
    }
    logger.info(yaml.dump([approver_data], indent=2, sort_keys=False))
