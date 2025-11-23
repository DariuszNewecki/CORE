# Changelog

All notable changes to this project will be documented in this file.

## [1.0.0] - A1 Release - 2023-10-01

### Added
- **A1 Autonomy Activated**: The system can now autonomously execute simple, self-healing tasks via the `micro-proposal` workflow.
- **Database as Single Source of Truth**: All operational knowledge (CLI commands, LLM resources, cognitive roles, domains) is now managed in a PostgreSQL database, eliminating YAML file drift.
- **Transactional Integration Workflow**: The `core-admin submit changes` command now performs a multi-stage, transactional integration process that is automatically rolled back on any failure, ensuring repository integrity.
- **Autonomous Capability Definition**: The system can now autonomously analyze new, untagged code and propose dot-notation capability keys using semantic context from its vector database.
- **Refactored CLI with Verb-Noun Grammar**: All `core-admin` commands have been refactored into a clear, predictable verb-noun structure (e.g., `check audit`, `manage database`).
- **Explicit Dependency Injection**: Introduced `CoreContext` to explicitly pass shared services, removing global singletons and improving testability.

### Changed
- **Consolidated Architecture**: Refactored `system/` and `agents/` directories into a clean, layered architecture under `src/` (`core`, `features`, `services`, `shared`).
- **Consolidated SQL Migrations**: All database migrations are now in a single, idempotent `001_consolidated_schema.sql` file for simplicity and clarity.
- **Upgraded to `pydantic-settings`**: Configuration management now uses the modern `pydantic-settings` for environment variable loading.

### Fixed
- **Vectorization Service**: The vectorization pipeline was repaired and now correctly uses `CognitiveService` for generating embeddings.
- **Numerous Import Paths**: Corrected dozens of import paths to align with the new, consolidated `src/` architecture.

## [1.1.0] - Encrypted Secrets & Autonomous Vectorization - 2025-01-16

### Added - Encrypted Secrets Management
- **Encrypted secrets storage** using Fernet (symmetric encryption) in PostgreSQL `core.runtime_settings` table
- **Complete CLI for secrets management** via `core-admin secrets` command:
  - `set` - Store encrypted secrets with audit trail
  - `get` - Retrieve secrets (with `--show` flag for viewing)
  - `list` - List all secret keys without exposing values
  - `delete` - Remove secrets with confirmation
  - `rotate` - Update secret values with rotation tracking
  - `migrate-from-env` - Batch migration from .env to encrypted storage
- **Audit trail** for all secret access logged to `core.agent_memory`
- **Backwards compatibility** with automatic fallback to .env if secret not in database

### Changed - LLM Services Now Use Encrypted Secrets
- **Updated `cognitive_service.py`** to read API keys from encrypted storage via `config_service.get_secret()`
- **Fixed LLMClient initialization** to properly initialize rate limiting semaphore
- **ConfigService renamed** from `ConfigurationService` to `ConfigService` for consistency
- **LLM services audit secret access** with context (e.g., "cognitive_service:deepseek_coder")

### Fixed - Vectorization & Autonomous Capability Definition
- **Fixed critical LLMClient initialization bug** that was blocking vectorization pipeline
- **Vectorized 190 symbols** successfully using encrypted API keys from database
- **AI autonomously defined 24 new capabilities** using DeepSeek Coder via encrypted credentials
- **Constitutional audit now passes** with 0 errors, 0 warnings, 0 unassigned symbols

### Migration Guide
```bash
# 1. Generate master encryption key
python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'

# 2. Add to .env
echo "CORE_MASTER_KEY=<your-key-here>" >> .env

# 3. Migrate existing API keys
poetry run core-admin secrets migrate-from-env

# 4. Verify migration
poetry run core-admin secrets list

# 5. Test LLM features work
poetry run core-admin search capabilities "test query"
```

### Impact
- **7 API keys** migrated from plain-text .env to encrypted database storage
- **System is now self-aware** with complete symbol vectorization and semantic search
- **Full autonomous capability definition** working end-to-end
- **Zero constitutional violations** - system is compliant and governable
- **Production-ready secrets management** with encryption, audit trails, and CLI tools

### Technical Debt Addressed
- Eliminated plain-text API keys in .env files
- Fixed long-standing LLMClient initialization pattern
- Cleaned up ConfigService naming inconsistency
- Established pattern for encrypted credential management

### Next Steps
- Test autonomous self-improvement loop with CORE proposing refactorings
- Clean up 159 pre-existing ruff linting violations
- Document autonomous development workflow
- Enable CORE to use encrypted secrets for all external service integrations
