# src/shared/infrastructure/repositories/db/common.py
"""
Provides common utilities for database-related CLI commands.

CONSTITUTIONAL AUTHORITY: Infrastructure (coordination)

AUTHORITY DEFINITION:
This module is infrastructure because it provides mechanical coordination
for database operations without making strategic decisions about what
migrations to run or how data should be structured.

RESPONSIBILITIES:
- Resolve where the migration assets live (the packaged ``shared._migrations``
  directory, ADR-162 D8) and load the migration manifest (policy)
- Retrieve git commit information

Asset location (D8, #1387): ``src/shared/_migrations/`` is the one source of
the migration assets -- ``infra/migrations/manifest.yaml``, the manifest's
``.sql`` files and ``schema.sql`` in that relative layout -- and it ships in
the wheel as package data. A source checkout and an installed wheel read the
same directory, so the migration set always matches the running code.

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
from dataclasses import dataclass
from typing import Literal

import yaml

from shared.config import settings
from shared.logger import getLogger
from shared.utils.subprocess_utils import run_command


logger = getLogger(__name__)

_MANIFEST_REL = pathlib.Path("infra") / "migrations" / "manifest.yaml"


_BUNDLE_PACKAGE = "shared._migrations"
_SCHEMA_SQL_REL = pathlib.Path("schema.sql")

# The assets are always read from the package; "bundled" names that origin in
# ``database status`` output (a source checkout reads the same package).
AssetOrigin = Literal["bundled"]


@dataclass(frozen=True)
# ID: 8921f01f-001e-4043-a6d4-501ae37fa60a
class MigrationAssets:
    """Where the manifest, the migration SQL and schema.sql are read from."""

    root: pathlib.Path
    origin: AssetOrigin = "bundled"

    @property
    # ID: da3b76bd-1279-426a-9b92-092c50f60654
    def manifest_path(self) -> pathlib.Path:
        return self.root / _MANIFEST_REL

    @property
    # ID: 5b5deb09-e584-4539-a873-2d0054e99450
    def schema_sql_path(self) -> pathlib.Path:
        return self.root / _SCHEMA_SQL_REL


def _bundled_root() -> pathlib.Path:
    # Same precedent as shared.config's machinery-floor lookup: the package is
    # a real directory both in a checkout (src/shared/_migrations) and in an
    # installed wheel (site-packages/shared/_migrations).
    return pathlib.Path(str(importlib.resources.files(_BUNDLE_PACKAGE)))


# ID: ea71c3ec-2c6d-47c7-ab72-8d3ec27e15fc
def resolve_migration_assets() -> MigrationAssets:
    """The packaged migration assets (``shared._migrations``, ADR-162 D8)."""
    root = _bundled_root()
    if not (root / _MANIFEST_REL).is_file():
        raise RuntimeError(
            "Migration assets are not in the shared._migrations package "
            f"({root}); the installed core-runtime is incomplete."
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
        res = run_command(["git", "rev-parse", "--verify", "HEAD"])
        if res.returncode == 0:
            return res.stdout.strip()[:40]
    except Exception as e:
        logger.debug("Git command failed, using settings fallback: %s", e)

    return str(getattr(settings, "GIT_COMMIT", "") or "").strip()[:40]
