# src/shared/infrastructure/repositories/db/common.py
"""
Provides common utilities for database-related CLI commands.

CONSTITUTIONAL AUTHORITY: Infrastructure (coordination)

AUTHORITY DEFINITION:
This module is infrastructure because it provides mechanical coordination
for database operations without making strategic decisions about what
migrations to run or how data should be structured.

RESPONSIBILITIES:
- Locate the repository root and load the migration manifest (policy)
- Retrieve git commit information

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

import pathlib
import subprocess

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
# Migration commands check for None and raise a helpful error at call time.
REPO_ROOT: pathlib.Path | None = _resolve_repo_root()


# ID: 80ae5adf-d9cc-432e-b962-369b8992c700
def load_policy() -> dict:
    """Load the migration manifest from infra/migrations/manifest.yaml."""
    if REPO_ROOT is None:
        raise RuntimeError(
            "Migration commands require the CORE source tree and cannot run "
            "from a pip-installed wheel. Clone the repository to use db migrate."
        )
    manifest_path = REPO_ROOT / _MANIFEST_REL
    return yaml.safe_load(manifest_path.read_text(encoding="utf-8"))


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
