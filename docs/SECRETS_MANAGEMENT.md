# Encrypted Secrets Management

**Status:** ✅ Production Ready (v1.1.0)
**Constitutional Authority:** `.intent/charter/policies/data/secrets_management_policy.yaml`

## Overview

CORE provides encrypted secrets management for API keys and sensitive credentials. All secrets are encrypted at rest using Fernet (symmetric encryption) and stored in PostgreSQL, with a complete audit trail for compliance and security.

## Why Encrypted Storage?

**Problems with plain-text .env files:**
- ❌ Accidentally committed to Git (exposed in history)
- ❌ No audit trail of who accessed what
- ❌ Difficult to rotate credentials
- ❌ No encryption at rest
- ❌ Hard to manage across environments

**Benefits of database storage:**
- ✅ Encrypted at rest with Fernet
- ✅ Complete audit trail (who, when, why)
- ✅ Easy rotation and migration
- ✅ Constitutional governance
- ✅ Programmatic access with fallback

## Quick Start

### 1. Generate Master Encryption Key

```bash
python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

**⚠️ CRITICAL:** Save this key securely! Without it, you cannot decrypt your secrets.

### 2. Add Key to Environment

```bash
# Add to .env (gitignored)
echo "CORE_MASTER_KEY=<your-generated-key>" >> .env
```

### 3. Migrate Existing Secrets

```bash
# Dry run to see what would be migrated
poetry run core-admin secrets migrate-from-env --dry-run

# Actually migrate
poetry run core-admin secrets migrate-from-env

# Verify migration
poetry run core-admin secrets list
```

### 4. Clean Up .env (Optional)

After migration, you can remove the plain-text API keys from `.env`. Keep only:
```bash
CORE_MASTER_KEY=<your-key>
# ... non-secret config ...
```

## CLI Commands

### Store a Secret

```bash
# Interactive (will prompt for value)
poetry run core-admin secrets set anthropic.api_key

# Non-interactive
poetry run core-admin secrets set anthropic.api_key --value "sk-ant-..."

# With description
poetry run core-admin secrets set anthropic.api_key \
  --value "sk-ant-..." \
  --description "Production API key"

# Force overwrite without confirmation
poetry run core-admin secrets set anthropic.api_key \
  --value "sk-ant-..." \
  --force
```

### Retrieve a Secret

```bash
# Check if secret exists (doesn't show value)
poetry run core-admin secrets get anthropic.api_key

# Show the actual value
poetry run core-admin secrets get anthropic.api_key --show
```

### List All Secrets

```bash
poetry run core-admin secrets list
```

Output shows keys, descriptions, and last updated timestamps (but NOT values).

### Delete a Secret

```bash
# With confirmation prompt
poetry run core-admin secrets delete old.api_key

# Skip confirmation
poetry run core-admin secrets delete old.api_key --yes
```

### Rotate a Secret

```bash
# Will prompt for new value
poetry run core-admin secrets rotate anthropic.api_key

# Non-interactive
poetry run core-admin secrets rotate anthropic.api_key \
  --new-value "sk-ant-new-key"
```

Rotation is logged in the audit trail with context.

### Migrate from .env File

```bash
# Preview what will be migrated
poetry run core-admin secrets migrate-from-env --dry-run

# Migrate from default .env
poetry run core-admin secrets migrate-from-env

# Migrate from specific file
poetry run core-admin secrets migrate-from-env --file .env.prod

# Overwrite existing secrets
poetry run core-admin secrets migrate-from-env --overwrite
```

## Programmatic Access

### In Your Code

```python
from core.secrets_service import get_secrets_service
from services.database.session_manager import get_session

async def my_function():
    async with get_session() as db:
        secrets_service = await get_secrets_service(db)

        # Get a secret (automatically decrypted)
        api_key = await secrets_service.get_secret(
            db,
            key="anthropic.api_key",
            audit_context="my_function"
        )

        # Use the API key
        # ... your code ...
```

### LLM Services (Automatic)

LLM services in `cognitive_service.py` automatically use encrypted secrets:

```python
# This now reads from encrypted storage
client = await cognitive_service.aget_client_for_role("CodeReviewer")
```

**Fallback:** If secret not found in database, falls back to `.env` for backwards compatibility.

## How It Works

### Architecture

```
┌─────────────────────────────────────────────────┐
│ CLI / Code                                      │
│  └─> get_secrets_service(db)                   │
│       └─> SecretsService(master_key)           │
│            ├─> encrypt(plaintext)              │
│            ├─> decrypt(ciphertext)             │
│            └─> audit_access(key, context)      │
└─────────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│ PostgreSQL: core.runtime_settings               │
│                                                 │
│  key (text)              | "anthropic.api_key" │
│  value (text)            | <encrypted-blob>    │
│  is_secret (boolean)     | true                │
│  description (text)      | "Production key"   │
│  last_updated (timestamp)| 2025-01-16 ...     │
└─────────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│ Audit Trail: core.agent_memory                  │
│                                                 │
│  cognitive_role | "cognitive_service:deepseek" │
│  memory_type    | "fact"                       │
│  content        | "Accessed secret: ..."       │
│  created_at     | 2025-01-16 ...               │
└─────────────────────────────────────────────────┘
```

### Encryption Details

- **Algorithm:** Fernet (symmetric encryption)
- **Key derivation:** Direct key usage (not password-based)
- **Storage:** Encrypted values in `core.runtime_settings.value`
- **Master key:** Stored in `CORE_MASTER_KEY` environment variable (NOT in database)

### Audit Trail

Every secret access is logged to `core.agent_memory` with:
- **Who:** The cognitive role or service accessing it
- **What:** The secret key (NOT the value)
- **When:** Timestamp
- **Why:** Context string (e.g., "cognitive_service:deepseek_coder")

Query audit logs:
```sql
SELECT cognitive_role, content, created_at
FROM core.agent_memory
WHERE content LIKE 'Accessed secret:%'
ORDER BY created_at DESC;
```

## Security Best Practices

### ✅ DO

- **Keep master key secure** - Store in password manager
- **Rotate secrets regularly** - Use `secrets rotate` command
- **Use audit trails** - Review who accessed what
- **Backup encrypted database** - Secrets are only in DB
- **Use descriptive keys** - `service.environment.purpose` format

### ❌ DON'T

- **Commit master key to Git** - It's in `.gitignore` for a reason
- **Share master key** - Each environment should have its own
- **Log secret values** - Only log keys, never values
- **Skip backups** - Losing DB = losing all secrets
- **Reuse keys across environments** - Dev/staging/prod should be separate

## Troubleshooting

### "CORE_MASTER_KEY not found"

```bash
# Verify key is set
echo $CORE_MASTER_KEY

# Add to .env if missing
echo "CORE_MASTER_KEY=<your-key>" >> .env
```

### "Decryption failed"

Wrong master key or corrupted data. Check:
1. Master key hasn't changed
2. Database connection is correct
3. Secret was encrypted with same key

### "Secret not found"

Secret doesn't exist in database. Options:
1. Create it: `poetry run core-admin secrets set <key>`
2. Check key name spelling
3. Verify not still in `.env` (fallback might be hiding it)

### Migration fails

```bash
# Check what would be migrated
poetry run core-admin secrets migrate-from-env --dry-run

# Common issues:
# - Master key not set
# - Secrets already exist (use --overwrite)
# - Database connection failed
```

## Constitutional Compliance

Secrets management follows these constitutional policies:

### secrets_management_policy.yaml

- **no_hardcoded_secrets:** Source code MUST NOT contain hardcoded secrets
- **redact_secrets_in_logs:** Logs MUST redact sensitive data

### database_policy.yaml

- **db.privacy.no_pii_or_secrets:** Secrets stored encrypted, not plain text
- **db.privacy.masking:** Audit logs never contain actual secret values

Verify compliance:
```bash
poetry run core-admin check audit
```

## Migration Guide

### From Plain-Text .env to Encrypted Storage

**Current state:** API keys in `.env` file
```bash
ANTHROPIC_CLAUDE_SONNET_API_KEY=sk-ant-...
DEEPSEEK_CHAT_API_KEY=sk-...
```

**Migration steps:**

1. **Generate master key**
   ```bash
   python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
   ```

2. **Add to .env**
   ```bash
   echo "CORE_MASTER_KEY=<generated-key>" >> .env
   ```

3. **Migrate secrets**
   ```bash
   poetry run core-admin secrets migrate-from-env
   ```

4. **Verify**
   ```bash
   poetry run core-admin secrets list
   poetry run core-admin secrets get ANTHROPIC_CLAUDE_SONNET_API_KEY --show
   ```

5. **Test LLM features**
   ```bash
   poetry run core-admin search capabilities "test"
   ```

6. **Clean up .env** (optional)
   - Remove migrated API keys
   - Keep only CORE_MASTER_KEY and non-secret config

7. **Rotate exposed keys** (if .env was ever committed)
   - Generate new API keys at provider
   - Update in database: `poetry run core-admin secrets rotate <key>`

### From Another Secrets Manager

If migrating from 1Password, AWS Secrets Manager, etc.:

```bash
# Export secrets to temporary file
# Format: KEY=value (one per line)

# Then migrate
poetry run core-admin secrets migrate-from-env --file exported_secrets.env

# Delete temporary file
rm exported_secrets.env
```

## FAQ

### Q: Can I use this in production?

**A:** Yes! The encryption is production-grade (Fernet), and the system includes audit trails and constitutional compliance.

### Q: What if I lose the master key?

**A:** You cannot decrypt secrets without it. **Back up your master key securely.**

### Q: How do I rotate the master key?

**A:** You'll need to:
1. Decrypt all secrets with old key
2. Re-encrypt with new key
3. Update CORE_MASTER_KEY
(We should add a command for this - create a GitHub issue!)

### Q: Can different services use different master keys?

**A:** Currently no - one master key per CORE instance. For multi-tenancy, run separate CORE instances.

### Q: Does this slow down LLM calls?

**A:** Negligible impact. Decryption happens once per service initialization, then cached in memory.

### Q: How do I back up secrets?

**A:** Back up your PostgreSQL database. Secrets are encrypted at rest, so backups are secure.

## Related Documentation

- [Database Policy](../.intent/charter/policies/data/database_policy.yaml)
- [Secrets Management Policy](../.intent/charter/policies/data/secrets_management_policy.yaml)
- [Configuration Management](./CONFIGURATION.md) *(coming soon)*
- [Security Best Practices](./SECURITY.md)

## Contributing

Found a bug? Want to improve secrets management?

1. Check [CONTRIBUTING.md](../CONTRIBUTING.md)
2. Create an issue on GitHub
3. Submit a PR with tests

## Version History

- **v1.1.0** (2025-01-16): Initial encrypted secrets implementation
  - Fernet encryption
  - Full CLI suite
  - LLM integration
  - Audit trails
  - Migration tools
