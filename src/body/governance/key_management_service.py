# src/body/governance/key_management_service.py
"""
Key Management Service - Body Layer Implementation.

CONSTITUTIONAL ALIGNMENT (V2.3.0):
- Relocated: Moved from Mind to Body to resolve architecture.mind.no_body_invocation.
- Responsibility: Executes cryptographic key generation and governed persistence.
- Governed: All writes route through FileService to maintain the audit trail.
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
    Generate a new Ed25519 key pair and persist it via the Body's FileService.
    """
    logger.info("🔑 Generating new key pair for identity: %s", identity)

    # Resolve paths via the provided resolver
    rel_key_dir = str(
        path_resolver.intent_root.relative_to(path_resolver.repo_root) / "keys"
    )

    rel_private_key_path = f"{rel_key_dir}/private.key"
    abs_private_key_path = path_resolver.repo_root / rel_private_key_path

    # Safety Gate
    if abs_private_key_path.exists() and not allow_overwrite:
        raise KeyManagementError(
            "A private key already exists. Use allow_overwrite to replace it.",
            exit_code=1,
        )

    # 1. Generate the Identity (Computational Work)
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    pem_private = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    # 2. Persist via Governed Mutation Surface (Body Execution)
    file_service.ensure_dir(rel_key_dir)
    file_service.write_runtime_bytes(rel_private_key_path, pem_private)

    # Set strict Unix permissions
    if abs_private_key_path.exists():
        os.chmod(abs_private_key_path, 0o600)

    pem_public = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    # 3. Output for the Operator
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
