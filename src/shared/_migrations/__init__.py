# src/shared/_migrations/__init__.py
"""The migration assets: their one source, shipped in the wheel (ADR-162 D8).

``infra/migrations/manifest.yaml``, every ``.sql`` file the manifest lists
under ``infra/scripts/migrations/`` (the manifest's ``directory:``, relative
to this package) and ``schema.sql`` are authored here and nowhere else
(#1387), so a source checkout and an installed wheel read the same files.
Resolved through
``shared.infrastructure.repositories.db.common.resolve_migration_assets``.
"""
