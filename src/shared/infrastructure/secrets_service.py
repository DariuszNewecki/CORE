# src/shared/infrastructure/secrets_service.py

"""
Encrypted secrets management service.
Stores API keys and sensitive config encrypted in the database.

Constitutional Principle: Safe by Default
- All secrets encrypted at rest using Fernet (symmetric encryption)
- Audit trail for all secret access
- Master key never stored in database
"""

from __future__ import annotations

from datetime import datetime

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import settings
from shared.exceptions import SecretNotFoundError
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: a7737c89-8e6c-4e99-bbed-2957c02471b1
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
    # ID: 87f34161-643a-4d73-9709-c017f28b5887
    def generate_master_key() -> str:
        """
        Generate a new Fernet master key.

        Returns:
            Base64-encoded key string (save to CORE_MASTER_KEY in .env)
        """
        return Fernet.generate_key().decode()

    # ID: 1e3c0bc6-e427-4e79-b874-2894af0e92c0
    def encrypt(self, plaintext: str) -> str:
        """Encrypt a secret value."""
        if not plaintext:
            raise ValueError("Cannot encrypt empty value")
        return self.cipher.encrypt(plaintext.encode()).decode()

    # ID: 1bf88613-80ca-4708-942a-a19470203aa6
    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a secret value."""
        if not ciphertext:
            raise ValueError("Cannot decrypt empty value")
        try:
            return self.cipher.decrypt(ciphertext.encode()).decode()
        except InvalidToken:
            raise ValueError("Decryption failed - wrong master key or corrupted data")

    # ID: 74ac4102-f3f3-4d30-9957-bab239b79c26
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
            "\n            INSERT INTO core.runtime_settings (key, value, description, is_secret, last_updated)\n            VALUES (:key, :value, :description, true, NOW())\n            ON CONFLICT (key)\n            DO UPDATE SET\n                value = EXCLUDED.value,\n                description = EXCLUDED.description,\n                last_updated = NOW()\n        "
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
        logger.info("Secret '%s' stored successfully (encrypted)", key)

    # ID: 57544a15-6f61-4058-b5ea-280618781666
    async def get_secret(
        self, db: AsyncSession, key: str, audit_context: str | None = None
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
            "\n            SELECT value FROM core.runtime_settings\n            WHERE key = :key AND is_secret = true\n        "
        )
        result = await db.execute(query, {"key": key})
        row = result.fetchone()
        if not row:
            raise SecretNotFoundError(key)
        await self._audit_secret_access(db, key, audit_context)
        return self.decrypt(row[0])

    # ID: 91ab22d7-7020-45ec-9258-0c46a37ff9d0
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
            "\n            DELETE FROM core.runtime_settings\n            WHERE key = :key AND is_secret = true\n        "
        )
        result = await db.execute(query, {"key": key})
        await db.commit()
        if result.rowcount == 0:
            raise SecretNotFoundError(key)
        logger.info("Secret '%s' deleted", key)

    # ID: 90950eb7-628f-4ec1-8e22-3c697a4b6642
    async def list_secrets(self, db: AsyncSession) -> list[dict]:
        """
        List all secret keys (not values!) in the database.

        Returns:
            List of dicts with 'key', 'description', 'last_updated'
        """
        query = text(
            "\n            SELECT key, description, last_updated\n            FROM core.runtime_settings\n            WHERE is_secret = true\n            ORDER BY key\n        "
        )
        result = await db.execute(query)
        return [
            {"key": row[0], "description": row[1], "last_updated": row[2]}
            for row in result.fetchall()
        ]

    # ID: de630750-18ed-4549-96c8-94153ca54fd7
    async def rotate_secret(self, db: AsyncSession, key: str, new_value: str) -> None:
        """
        Rotate a secret (change its value).

        This is a convenience method that archives the old value
        and sets the new one.

        Args:
            db: Database session
            key: Secret identifier
            new_value: New plaintext secret value
        """
        try:
            old_value = await self.get_secret(db, key, audit_context="rotation")
            logger.info("Rotating secret '%s' (old value archived)", key)
        except SecretNotFoundError:
            logger.warning("Rotating secret '%s' (no previous value)", key)
        await self.set_secret(
            db,
            key,
            new_value,
            description=f"Rotated on {datetime.utcnow()}",
            audit_context="rotation",
        )

    async def _audit_secret_access(
        self, db: AsyncSession, key: str, context: str | None
    ) -> None:
        """
        Log secret access for audit trail.

        This creates a record in agent_memory for forensics.
        """
        try:
            query = text(
                "\n                INSERT INTO core.agent_memory (\n                    cognitive_role,\n                    memory_type,\n                    content,\n                    relevance_score,\n                    created_at\n                ) VALUES (\n                    :role,\n                    'fact',\n                    :content,\n                    1.0,\n                    NOW()\n                )\n            "
            )
            await db.execute(
                query,
                {"role": context or "system", "content": f"Accessed secret: {key}"},
            )
        except Exception as e:
            logger.error("Failed to audit secret access: %s", e)

    @staticmethod
    # ID: a5c634df-816c-4843-a94a-1e2ffc92b998
    async def migrate_from_env(
        db: AsyncSession, env_vars: dict[str, str], master_key: str
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
        env_to_db_key = {
            "ANTHROPIC_CLAUDE_SONNET_API_KEY": "anthropic.api_key",
            "DEEPSEEK_CHAT_API_KEY": "deepseek_chat.api_key",
            "DEEPSEEK_CODER_API_KEY": "deepseek_coder.api_key",
            "OLLAMA_LOCAL_API_KEY": "ollama.api_key",
            "LOCAL_EMBEDDING_API_KEY": "embedding.api_key",
        }
        for env_name, db_key in env_to_db_key.items():
            if env_vars.get(env_name):
                await service.set_secret(
                    db,
                    db_key,
                    env_vars[env_name],
                    description=f"Migrated from {env_name}",
                )
                migrated[env_name] = db_key
                logger.info("Migrated {env_name} → %s", db_key)
        return migrated


# ID: a2beeaad-c05f-404b-8215-0e999d48a4d3
async def get_secrets_service(db: AsyncSession) -> SecretsService:
    """
    Factory function to create SecretsService with master key from settings.

    This is the primary way to instantiate the service in production code.

    Usage:
        secrets = await get_secrets_service(db)
        api_key = await secrets.get_secret(db, "anthropic.api_key")

    Raises:
        RuntimeError: If CORE_MASTER_KEY not set in settings configuration
    """
    master_key = settings.CORE_MASTER_KEY
    if not master_key:
        raise RuntimeError(
            "CORE_MASTER_KEY not found in configuration. Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
        )
    return SecretsService(master_key)
