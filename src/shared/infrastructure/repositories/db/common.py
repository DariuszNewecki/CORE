# src/shared/infrastructure/repositories/db/common.py
"""
Provides common utilities for database-related CLI commands.

CONSTITUTIONAL AUTHORITY: Infrastructure (coordination)

AUTHORITY DEFINITION:
This module is infrastructure because it provides mechanical coordination
for database operations without making strategic decisions about what
migrations to run or how data should be structured.

RESPONSIBILITIES:
- Resolve where the migration assets live (source checkout or the wheel's
  bundled mirror, ADR-162 D8) and load the migration manifest (policy)
- Retrieve git commit information

Asset precedence (D8): **bundled-first when running from a wheel** -- the
migration set must match the installed code -- and the source tree when the
package *is* the checkout (editable install). ``src/shared/_migrations/`` is
a byte-parity mirror of ``infra/migrations/manifest.yaml``, the manifest's
``.sql`` files and ``schema.sql`` in the same relative layout.

Ledger reads/writes and migration execution live in ``ledger_engine`` (ADR-162
D7: one transaction per migration, advisory-locked); the typed manifest view
lives in ``manifest``.

AUTHORITY LIMITS:
- Cannot decide which migrations should be applied (strategic)
- Cannot interpret the semantic meaning of migrations
- Cannot choose between alternative migration strategies
- Cannot make business logic decisions about schema design

EXEMPTIONS:
- May access database directly (infrastructure coordination)
- May access filesystem for migration files
- Exempt from Mind/Body/Will layer restrictions (infrastructure role)
- Subject to infrastructure authority boundary rules

Refactored to comply with operations.runtime.env_vars_defined (no os.getenv).

See: .specs/papers/CORE-Infrastructure-Definition.md Section 5
"""

from __future__ import annotations

import importlib.resources
import pathlib
import subprocess
from dataclasses import dataclass
from typing import Literal

import yaml

from shared.config import settings
from shared.logger import getLogger


logger = getLogger(__name__)

_MANIFEST_REL = pathlib.Path("infra") / "migrations" / "manifest.yaml"


# This robust function finds the project root without relying on the global settings object.
def _get_repo_root_for_migration() -> pathlib.Path:
    """Finds the repo root by searching upwards for a known marker file."""
    current_path = pathlib.Path(__file__).resolve()
    for parent in [current_path, *current_path.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    raise RuntimeError("Could not determine the repository root for migration.")


def _resolve_repo_root() -> pathlib.Path | None:
    """Return the migration repo root, or None when running as an installed wheel."""
    try:
        return _get_repo_root_for_migration()
    except RuntimeError:
        return None


# Lazy sentinel — None when running as a pip-installed wheel outside the source tree.
REPO_ROOT: pathlib.Path | None = _resolve_repo_root()

_BUNDLE_PACKAGE = "shared._migrations"
_SCHEMA_SQL_REL = pathlib.Path("schema.sql")

AssetOrigin = Literal["source", "bundled"]


@dataclass(frozen=True)
# ID: 8921f01f-001e-4043-a6d4-501ae37fa60a
class MigrationAssets:
    """Where the manifest, the migration SQL and schema.sql are read from."""

    root: pathlib.Path
    origin: AssetOrigin

    @property
    # ID: da3b76bd-1279-426a-9b92-092c50f60654
    def manifest_path(self) -> pathlib.Path:
        return self.root / _MANIFEST_REL

    @property
    # ID: 5b5deb09-e584-4539-a873-2d0054e99450
    def schema_sql_path(self) -> pathlib.Path:
        return self.root / _SCHEMA_SQL_REL


def _bundled_root() -> pathlib.Path:
    # Same precedent as shared.config's machinery-floor lookup: an installed
    # wheel exposes package data as a real directory.
    return pathlib.Path(str(importlib.resources.files(_BUNDLE_PACKAGE)))


# ID: ea71c3ec-2c6d-47c7-ab72-8d3ec27e15fc
def resolve_migration_assets() -> MigrationAssets:
    """Source tree when the package is the checkout; the bundle otherwise (D8)."""
    if REPO_ROOT is not None:
        return MigrationAssets(root=REPO_ROOT, origin="source")
    root = _bundled_root()
    if not (root / _MANIFEST_REL).is_file():
        raise RuntimeError(
            "Migration assets are neither a source checkout nor bundled in this "
            f"installation ({root}); the installed core-runtime is incomplete."
        )
    return MigrationAssets(root=root, origin="bundled")


# ID: 80ae5adf-d9cc-432e-b962-369b8992c700
def load_policy(assets: MigrationAssets | None = None) -> dict:
    """Load the migration manifest (infra/migrations/manifest.yaml) as a mapping."""
    assets = assets or resolve_migration_assets()
    return yaml.safe_load(assets.manifest_path.read_text(encoding="utf-8"))


# ID: c0a84f36-7546-405b-8de4-eba8548ff56b
def git_commit_sha() -> str:
    """Best-effort: get current commit SHA via CLI or Settings."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0:
            return res.stdout.strip()[:40]
    except Exception as e:
        logger.debug("Git command failed, using settings fallback: %s", e)

    return str(getattr(settings, "GIT_COMMIT", "") or "").strip()[:40]
