# src/shared/_migrations/__init__.py
"""Wheel-side mirror of the migration assets (ADR-162 D8, U7).

Package data, not a source of truth: ``infra/migrations/manifest.yaml``,
every ``.sql`` file the manifest lists under ``infra/scripts/migrations/``
and the repository-root ``schema.sql`` are copied here byte for byte in the
same relative layout, so the ledger engine resolves paths identically from a
source checkout and from an installed wheel. The parity test
(``tests/infra/test_migrations_ship_in_wheel.py``) enforces that every
change updates source and mirror in the same commit; there is no runtime
synchronisation. Resolved through
``shared.infrastructure.repositories.db.common.resolve_migration_assets``.
"""
