# src/shared/infrastructure/repositories/db/common.py
# ID: infra.repo.db.common
"""
Provides common utilities for database-related CLI commands.
Refactored to comply with operations.runtime.env_vars_defined (no os.getenv).
"""

from __future__ import annotations

import pathlib
import subprocess
from datetime import UTC, datetime

import sqlparse
from sqlalchemy import text

from shared.config import settings
from shared.infrastructure.database.session_manager import get_session
from shared.processors.yaml_processor import strict_yaml_processor


# This robust function finds the project root without relying on the global settings object.
def _get_repo_root_for_migration() -> pathlib.Path:
    """Finds the repo root by searching upwards for a known marker file."""
    current_path = pathlib.Path(__file__).resolve()
    for parent in [current_path, *current_path.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    raise RuntimeError("Could not determine the repository root for migration.")


REPO_ROOT = _get_repo_root_for_migration()


# ID: 80ae5adf-d9cc-432e-b962-369b8992c700
def load_policy() -> dict:
    """Load the database_policy.yaml using a minimal, self-contained pathfinder."""
    policy_path = settings.paths.policy("data/governance")
    return strict_yaml_processor.load_strict(policy_path)


# ID: a5ec72d4-d489-434f-ad69-a36a39229d92
async def ensure_ledger() -> None:
    """Ensure core schema and the migrations ledger table exist."""
    async with get_session() as session:
        async with session.begin():
            await session.execute(text("create schema if not exists core"))
            await session.execute(
                text(
                    """
                    create table if not exists core._migrations (
                      id text primary key,
                      applied_at timestamptz not null default now()
                    )
                    """
                )
            )


# ID: ec3e6b37-b4e8-4870-80f5-10d652ac5902
async def get_applied() -> set[str]:
    """Return set of applied migration IDs."""
    async with get_session() as session:
        result = await session.execute(text("select id from core._migrations"))
        return {r[0] for r in result}


# ID: 27163ec0-f952-4ed7-938b-080473bee2eb
async def apply_sql_file(path: pathlib.Path) -> None:
    """Apply a .sql file by splitting into single statements (asyncpg-safe)."""
    sql_text = path.read_text(encoding="utf-8")
    statements: list[str] = [s.strip() for s in sqlparse.split(sql_text) if s.strip()]
    async with get_session() as session:
        async with session.begin():
            for stmt in statements:
                await session.execute(text(stmt))


# ID: e3cbb291-e852-4ad5-bcc3-8b4046c1def0
async def record_applied(mig_id: str) -> None:
    """Record a migration as applied."""
    async with get_session() as session:
        async with session.begin():
            await session.execute(
                text(
                    "insert into core._migrations (id, applied_at) values (:id, :ts)"
                ).bindparams(id=mig_id, ts=datetime.now(tz=UTC))
            )


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
    except Exception:
        pass

    # CONSTITUTIONAL FIX: Use Settings instead of os.getenv
    return str(getattr(settings, "GIT_COMMIT", "") or "").strip()[:40]
