# src/system/admin/keys.py
"""
Intent: Key management commands for the CORE Admin CLI.
Provides Ed25519 key generation and helper output for approver configuration.
"""

from __future__ import annotations

import os

import typer
import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from shared.config import settings
from shared.logger import getLogger

log = getLogger("core_admin")


def register(app: typer.Typer) -> None:
    """Intent: Register key management commands under the admin CLI."""

    @app.command("keygen")
    def keygen(
        identity: str = typer.Argument(
            help="Identity for the key pair (e.g., 'your.name@example.com')."
        ),
    ) -> None:
        """Intent: Generate a new Ed25519 key pair and print an approver YAML block."""
        log.info(f"🔑 Generating new key pair for identity: {identity}")
        settings.KEY_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        private_key_path = settings.KEY_STORAGE_DIR / "private.key"

        if private_key_path.exists():
            typer.confirm(
                "⚠️ A private key already exists. Overwriting it will invalidate your old identity. Continue?",
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
            "\n📋 Add the following YAML block to '.intent/constitution/approvers.yaml' under 'approvers':\n"
        )

        approver_yaml = yaml.dump(
            [
                {
                    "identity": identity,
                    "public_key": pem_public.decode("utf-8"),
                    "role": "maintainer",
                    "description": "Primary maintainer",
                }
            ],
            indent=2,
        )
        print(approver_yaml)
