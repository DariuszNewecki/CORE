# src/features/governance/key_management_service.py
"""
Intent: Key management commands for the CORE Admin CLI.
Provides Ed25519 key generation and helper output for approver configuration.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import typer
import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from shared.config import settings
from shared.logger import getLogger

log = getLogger("core_admin.keys")


# The @typer.run decorator has been removed. The function is now a standard function.
# ID: b02176d9-c38f-4447-9ad5-ef17d6648263
def keygen(
    identity: str = typer.Argument(
        ..., help="Identity for the key pair (e.g., 'your.name@example.com')."
    ),
) -> None:
    """Intent: Generate a new Ed25519 key pair and print an approver YAML block."""
    log.info(f"🔑 Generating new key pair for identity: {identity}")

    key_storage_dir = settings.REPO_PATH / settings.KEY_STORAGE_DIR
    key_storage_dir.mkdir(parents=True, exist_ok=True)
    private_key_path = key_storage_dir / "private.key"

    if private_key_path.exists():
        typer.confirm(
            "⚠️ A private key already exists. Overwriting it will invalidate your "
            "old identity. Continue?",
            abort=True,
        )

    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    pem_private = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    private_key_path.write_bytes(pem_private)
    os.chmod(private_key_path, 0o600)

    pem_public = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    log.info(f"\n✅ Private key saved securely to: {private_key_path}")
    log.info(
        "\n📋 Add the following YAML block to "
        "'.intent/constitution/approvers.yaml' under 'approvers':\n"
    )

    approver_data = {
        "identity": identity,
        "public_key": pem_public.decode("utf-8"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "role": "maintainer",
        "description": "Primary maintainer",
    }
    print(yaml.dump([approver_data], indent=2, sort_keys=False))
