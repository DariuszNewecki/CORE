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