# src/core/secrets_service.py
"""
Encrypted secrets management service.
Stores API keys and sensitive config encrypted in the database.

Constitutional Principle: Safe by Default
- All secrets encrypted at rest using Fernet (symmetric encryption)
- Audit trail for all secret access
- Master key never stored in database
"""

from __future__ import annotations

import os
from datetime import datetime

from cryptography.fernet import Fernet, InvalidToken
from shared.exceptions import SecretNotFoundError
from shared.logger import getLogger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

log = getLogger(__name__)


# ID: secrets-service-001
# ID: 3b635f48-6792-4a07-9fb1-0a90461d26cd
class SecretsService:
    """
    Manages encrypted secrets in the database.

    Usage:
        secrets = SecretsService(master_key)
        await secrets.set_secret(db, "anthropic.api_key", "sk-ant-...")
        api_key = await secrets.get_secret(db, "anthropic.api_key")
    """

    def __init__(self, master_key: str):
        """
        Initialize with master encryption key.

        Args:
            master_key: Base64-encoded Fernet key (generate with: Fernet.generate_key())

        Raises:
            ValueError: If master_key is invalid
        """
        try:
            self.cipher = Fernet(master_key.encode())
        except Exception as e:
            raise ValueError(f"Invalid master key format: {e}")

    @staticmethod
    # ID: 0ca1b655-8522-413e-9668-a699b68ca224
    def generate_master_key() -> str:
        """
        Generate a new Fernet master key.

        Returns:
            Base64-encoded key string (save to CORE_MASTER_KEY in .env)
        """
        return Fernet.generate_key().decode()

    # ID: dc8eadd9-5dab-4369-b598-9773cd967e51
    def encrypt(self, plaintext: str) -> str:
        """Encrypt a secret value."""
        if not plaintext:
            raise ValueError("Cannot encrypt empty value")
        return self.cipher.encrypt(plaintext.encode()).decode()

    # ID: 9f41551a-9871-45c7-848b-5a4fcaae66be
    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a secret value."""
        if not ciphertext:
            raise ValueError("Cannot decrypt empty value")
        try:
            return self.cipher.decrypt(ciphertext.encode()).decode()
        except InvalidToken:
            raise ValueError("Decryption failed - wrong master key or corrupted data")

    # ID: 7a53be29-a1e2-4880-acb5-55b5b97f990f
    async def set_secret(
        self,
        db: AsyncSession,
        key: str,
        value: str,
        description: str | None = None,
        audit_context: str | None = None,
    ) -> None:
        """
        Store an encrypted secret in the database.

        Args:
            db: Database session
            key: Secret identifier (e.g., "anthropic.api_key")
            value: Plaintext secret value
            description: Optional human-readable description
            audit_context: Optional context for audit log
        """
        encrypted_value = self.encrypt(value)

        query = text(
            """
            INSERT INTO core.runtime_settings (key, value, description, is_secret, last_updated)
            VALUES (:key, :value, :description, true, NOW())
            ON CONFLICT (key)
            DO UPDATE SET
                value = EXCLUDED.value,
                description = EXCLUDED.description,
                last_updated = NOW()
        """
        )

        await db.execute(
            query,
            {
                "key": key,
                "value": encrypted_value,
                "description": description or f"Encrypted secret: {key}",
            },
        )
        await db.commit()

        log.info(f"Secret '{key}' stored successfully (encrypted)")

    # ID: a9f6d951-fcac-4bcb-9d30-f70c388da777
    async def get_secret(
        self,
        db: AsyncSession,
        key: str,
        audit_context: str | None = None,
    ) -> str:
        """
        Retrieve and decrypt a secret from the database.

        Args:
            db: Database session
            key: Secret identifier
            audit_context: Optional context for audit log (e.g., "planner_agent")

        Returns:
            Decrypted secret value

        Raises:
            SecretNotFoundError: If secret not found
            ValueError: If decryption fails
        """
        query = text(
            """
            SELECT value FROM core.runtime_settings
            WHERE key = :key AND is_secret = true
        """
        )

        result = await db.execute(query, {"key": key})
        row = result.fetchone()

        if not row:
            raise SecretNotFoundError(key)

        # Audit the access
        await self._audit_secret_access(db, key, audit_context)

        # Decrypt and return
        return self.decrypt(row[0])

    # ID: ccd364c2-e3b2-4f44-8c7a-183f5a1d9e58
    async def delete_secret(self, db: AsyncSession, key: str) -> None:
        """
        Delete a secret from the database.

        Args:
            db: Database session
            key: Secret identifier

        Raises:
            SecretNotFoundError: If secret not found
        """
        query = text(
            """
            DELETE FROM core.runtime_settings
            WHERE key = :key AND is_secret = true
        """
        )

        result = await db.execute(query, {"key": key})
        await db.commit()

        if result.rowcount == 0:
            raise SecretNotFoundError(key)

        log.info(f"Secret '{key}' deleted")

    # ID: 5a325326-dfed-4fa6-b4d7-0496a59d79d3
    async def list_secrets(self, db: AsyncSession) -> list[dict]:
        """
        List all secret keys (not values!) in the database.

        Returns:
            List of dicts with 'key', 'description', 'last_updated'
        """
        query = text(
            """
            SELECT key, description, last_updated
            FROM core.runtime_settings
            WHERE is_secret = true
            ORDER BY key
        """
        )

        result = await db.execute(query)
        return [
            {
                "key": row[0],
                "description": row[1],
                "last_updated": row[2],
            }
            for row in result.fetchall()
        ]

    # ID: 9c6290c5-faca-4ccf-a8c6-e11d785a1633
    async def rotate_secret(
        self,
        db: AsyncSession,
        key: str,
        new_value: str,
    ) -> None:
        """
        Rotate a secret (change its value).

        This is a convenience method that archives the old value
        and sets the new one.

        Args:
            db: Database session
            key: Secret identifier
            new_value: New plaintext secret value
        """
        # Archive old value (optional - for audit trail)
        try:
            old_value = await self.get_secret(db, key, audit_context="rotation")
            log.info(f"Rotating secret '{key}' (old value archived)")
        except SecretNotFoundError:
            log.warning(f"Rotating secret '{key}' (no previous value)")

        # Set new value
        await self.set_secret(
            db,
            key,
            new_value,
            description=f"Rotated on {datetime.utcnow()}",
            audit_context="rotation",
        )

    async def _audit_secret_access(
        self,
        db: AsyncSession,
        key: str,
        context: str | None,
    ) -> None:
        """
        Log secret access for audit trail.

        This creates a record in agent_memory for forensics.
        """
        try:
            query = text(
                """
                INSERT INTO core.agent_memory (
                    cognitive_role,
                    memory_type,
                    content,
                    relevance_score,
                    created_at
                ) VALUES (
                    :role,
                    'fact',
                    :content,
                    1.0,
                    NOW()
                )
            """
            )

            await db.execute(
                query,
                {
                    "role": context or "system",
                    "content": f"Accessed secret: {key}",
                },
            )
            # Don't commit here - let the caller control transaction
        except Exception as e:
            # Don't fail secret retrieval if audit fails
            log.error(f"Failed to audit secret access: {e}")

    @staticmethod
    # ID: 7fe8f54c-1a07-430d-9870-49fc93ab5bf5
    async def migrate_from_env(
        db: AsyncSession,
        env_vars: dict[str, str],
        master_key: str,
    ) -> dict[str, str]:
        """
        Migrate secrets from environment variables to encrypted database.

        Args:
            db: Database session
            env_vars: Dict of env var names to values (e.g., {"ANTHROPIC_API_KEY": "sk-..."})
            master_key: Master encryption key

        Returns:
            Dict of migrated keys to their new database keys
        """
        service = SecretsService(master_key)
        migrated = {}

        # Map env var names to database keys
        env_to_db_key = {
            "ANTHROPIC_CLAUDE_SONNET_API_KEY": "anthropic.api_key",
            "DEEPSEEK_CHAT_API_KEY": "deepseek_chat.api_key",
            "DEEPSEEK_CODER_API_KEY": "deepseek_coder.api_key",
            "OLLAMA_LOCAL_API_KEY": "ollama.api_key",
            "LOCAL_EMBEDDING_API_KEY": "embedding.api_key",
        }

        for env_name, db_key in env_to_db_key.items():
            if env_name in env_vars and env_vars[env_name]:
                await service.set_secret(
                    db,
                    db_key,
                    env_vars[env_name],
                    description=f"Migrated from {env_name}",
                )
                migrated[env_name] = db_key
                log.info(f"Migrated {env_name} → {db_key}")

        return migrated


# ID: secrets-service-002
# ID: ec3157ed-0084-441f-934c-a6646eae6942
async def get_secrets_service(db: AsyncSession) -> SecretsService:
    """
    Factory function to create SecretsService with master key from environment.

    This is the primary way to instantiate the service in production code.

    Usage:
        secrets = await get_secrets_service(db)
        api_key = await secrets.get_secret(db, "anthropic.api_key")

    Raises:
        RuntimeError: If CORE_MASTER_KEY not set in environment
    """
    master_key = os.getenv("CORE_MASTER_KEY")
    if not master_key:
        raise RuntimeError(
            "CORE_MASTER_KEY not found in environment. "
            "Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
        )

    return SecretsService(master_key)
