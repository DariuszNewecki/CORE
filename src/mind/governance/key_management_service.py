# src/mind/governance/key_management_service.py
"""
Intent: Key management commands for the CORE Admin CLI.
Provides Ed25519 key generation and helper output for approver configuration.

CONSTITUTIONAL FIX:
- Aligned with 'governance.artifact_mutation.traceable'.
- NO LONGER imports FileHandler - uses FileService from Body layer
- Enforces IntentGuard and audit logging for security identity creation.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from body.services.file_service import FileService
from shared.exceptions import CoreError
from shared.logger import getLogger
from shared.path_resolver import PathResolver


logger = getLogger(__name__)
log = logger  # keep tests and tools happy


# ID: 8a1d1403-b439-475e-a712-cc7c687f6cb9
class KeyManagementError(CoreError):
    """Raised when key management operations fail."""


# ID: f8491062-091f-49e6-acbf-9b3ee994409e
def keygen(
    identity: str,
    *,
    path_resolver: PathResolver,
    file_service: FileService,
    allow_overwrite: bool = False,
) -> None:
    """
    Intent: Generate a new Ed25519 key pair and print an approver YAML block.

    CONSTITUTIONAL FIX: Changed parameter from FileHandler to FileService

    Args:
        identity: Identity name for the key
        path_resolver: PathResolver for path resolution
        file_service: Body layer FileService for file operations
        allow_overwrite: Whether to overwrite existing key
    """
    logger.info("🔑 Generating new key pair for identity: %s", identity)

    rel_key_dir = str(
        path_resolver.intent_root.relative_to(path_resolver.repo_root) / "keys"
    )

    rel_private_key_path = f"{rel_key_dir}/private.key"
    abs_private_key_path = path_resolver.repo_root / rel_private_key_path

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

    # CONSTITUTIONAL FIX: Governed directory creation and write via FileService
    file_service.ensure_dir(rel_key_dir)
    file_service.write_runtime_bytes(rel_private_key_path, pem_private)

    # Ensure strict permissions on the resulting file
    if abs_private_key_path.exists():
        os.chmod(abs_private_key_path, 0o600)

    pem_public = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    logger.info(
        "\n✅ Private key saved securely via FileService to: %s", rel_private_key_path
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
