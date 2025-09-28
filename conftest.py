# conftest.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest
import yaml


# ------------------------
# Global, per-test defaults
# ------------------------
@pytest.fixture(autouse=True)
def _core_env_defaults(monkeypatch):
    """Harmless defaults so Settings() never explodes during tests."""
    monkeypatch.setenv("QDRANT_URL", "http://localhost:6333")
    monkeypatch.setenv("QDRANT_COLLECTION_NAME", "core_capabilities")
    monkeypatch.setenv("LOCAL_EMBEDDING_API_URL", "http://localhost:11434")
    monkeypatch.setenv("LOCAL_EMBEDDING_MODEL_NAME", "test-embed")
    monkeypatch.setenv("LOCAL_EMBEDDING_DIM", "384")


# ------------------------
# Basic repo sandbox
# ------------------------
@pytest.fixture
def mock_core_env(tmp_path: Path, monkeypatch) -> Path:
    """Minimal repo sandbox each test can use as its working directory."""
    repo: Path = tmp_path
    (repo / "src").mkdir(parents=True, exist_ok=True)
    (repo / ".intent").mkdir(parents=True, exist_ok=True)

    # Run tests from this repo
    monkeypatch.chdir(repo)

    # Point Settings to this repo root (lazy import to avoid side-effects)
    from shared.config import settings
    settings.initialize_for_test(repo)

    return repo


# ------------------------
# DB session for tests that insert rows
# ------------------------
@pytest.fixture
async def get_test_session(mock_core_env: Path, monkeypatch):
    """
    Async SQLAlchemy session bound to a file-based SQLite DB under the test repo.
    Using a file (not :memory:) ensures the same DB is seen by both the service
    and the test code.
    """
    db_path = mock_core_env / "test.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", db_url)

    # Import model Base and tables (try both likely module paths)
    try:
        from core.db.models import Base, LlmResource, CognitiveRole  # noqa: F401
    except Exception:
        from core.models import Base, LlmResource, CognitiveRole  # type: ignore  # noqa: F401

    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

    engine = create_async_engine(db_url, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, expire_on_commit=False)
    session = Session()

    try:
        yield session
    finally:
        await session.close()
        await engine.dispose()


# ------------------------
# Minimal constitution/files for planner tests
# ------------------------
@pytest.fixture
def mock_fs_with_constitution(mock_core_env: Path):
    """Prepare a minimal constitution so planner tests can run."""
    repo = mock_core_env

    (repo / "mind" / "prompts").mkdir(parents=True, exist_ok=True)
    (repo / "charter" / "policies" / "governance").mkdir(parents=True, exist_ok=True)

    meta: Dict[str, Any] = {
        "mind": {
            "prompts": {
                "planner_agent": "mind/prompts/planner_agent.prompt",
            }
        },
        "charter": {
            "policies": {
                "governance": {
                    "available_actions_policy": "charter/policies/governance/available_actions_policy.yaml"
                }
            }
        },
    }
    (repo / ".intent" / "meta.yaml").write_text(
        yaml.safe_dump(meta), encoding="utf-8"
    )

    (repo / "mind" / "prompts" / "planner_agent.prompt").write_text(
        "Plan for: {goal}\n{reconnaissance_report}\n{action_descriptions}\nReturn JSON only.",
        encoding="utf-8",
    )

    available_actions = {
        "actions": [
            {
                "name": "create_file",
                "description": "Create a source file with given content.",
                "parameters": [
                    {
                        "name": "file_path",
                        "type": "string",
                        "required": True,
                        "description": "Path to file",
                    },
                    {
                        "name": "content",
                        "type": "string",
                        "required": False,
                        "description": "File content",
                    },
                ],
            }
        ]
    }
    (repo / "charter" / "policies" / "governance" / "available_actions_policy.yaml").write_text(
        yaml.safe_dump(available_actions), encoding="utf-8"
    )

    # Ensure Settings sees the new meta
    from shared.config import settings
    settings.initialize_for_test(repo)

    return repo
