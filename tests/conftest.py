# tests/conftest.py
"""
Central pytest configuration and fixtures for the CORE project.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest
import sqlparse
import yaml
from dotenv import load_dotenv
from shared.config import settings
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# --- THIS IS THE CRITICAL FIX: Ensure .env.test is loaded FIRST ---
# This guarantees that os.getenv() will have the correct values for the test session.
load_dotenv(".env.test", override=True)
os.environ.setdefault("CORE_ENV", "TEST")


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_fs_with_constitution(tmp_path: Path) -> Path:
    intent_dir = tmp_path / ".intent"
    charter_dir = intent_dir / "charter"
    policies_dir = charter_dir / "policies"
    agent_policies_dir = policies_dir / "agent"
    governance_policies_dir = policies_dir / "governance"
    mind_dir = intent_dir / "mind"
    prompts_dir = mind_dir / "prompts"
    for p in [agent_policies_dir, governance_policies_dir, prompts_dir]:
        p.mkdir(parents=True, exist_ok=True)
    (tmp_path / ".git").mkdir()
    meta_content = {
        "charter": {
            "policies": {
                "agent": {
                    "micro_proposal_policy": "charter/policies/agent/micro_proposal_policy.yaml",
                    "agent_policy": "charter/policies/agent/agent_policy.yaml",
                },
                "governance": {
                    "available_actions_policy": "charter/policies/governance/available_actions_policy.yaml"
                },
            }
        },
        "mind": {
            "prompts": {
                "planner_agent": "mind/prompts/planner_agent.prompt",
                "micro_planner": "mind/prompts/micro_planner.prompt",
            }
        },
    }
    (intent_dir / "meta.yaml").write_text(yaml.dump(meta_content))
    available_actions_content = {
        "policy_id": "mock-uuid-actions",
        "id": "available_actions_policy",
        "version": "1.0.0",
        "title": "Mock Actions",
        "purpose": "...",
        "status": "active",
        "owners": {"primary": "test"},
        "review": {"frequency": "annual"},
        "actions": [
            {
                "name": "create_file",
                "description": "Creates a file.",
                "parameters": [{"name": "file_path", "type": "string"}],
            },
            {
                "name": "autonomy.self_healing.format_code",
                "description": "Formats code.",
                "parameters": [{"name": "file_path", "type": "string"}],
            },
        ],
    }
    (governance_policies_dir / "available_actions_policy.yaml").write_text(
        yaml.dump(available_actions_content)
    )
    (agent_policies_dir / "micro_proposal_policy.yaml").write_text(
        "policy_id: mock-uuid\nid: micro_proposal_policy\nversion: '1.0.0'\n"
    )
    (agent_policies_dir / "agent_policy.yaml").write_text(
        "policy_id: mock-uuid-agent\nid: agent_policy\nversion: '1.0.0'\n"
    )
    (prompts_dir / "planner_agent.prompt").write_text("Plan for: {goal}")

    # --- THIS FIXES THE KeyError: 'goal' ---
    # The agent code expects the placeholder to be 'user_goal'.
    (prompts_dir / "micro_planner.prompt").write_text(
        "Create micro-plan for: {user_goal}"
    )

    return tmp_path


@pytest.fixture
def mock_core_env(mock_fs_with_constitution: Path, monkeypatch) -> Path:
    monkeypatch.setattr(settings, "REPO_PATH", mock_fs_with_constitution)
    settings.initialize_for_test(mock_fs_with_constitution)
    return mock_fs_with_constitution


@pytest.fixture(scope="function")
async def get_test_session(monkeypatch) -> AsyncSession:
    # --- THIS FIXTURE IS NOW ROBUST ---
    raw_db_url = os.getenv("DATABASE_URL")
    if not raw_db_url:
        pytest.fail("DATABASE_URL not found. Ensure it is set in your .env.test file.")

    # Use os.path.expandvars to correctly substitute $VAR style variables
    db_url = os.path.expandvars(raw_db_url)

    # Safety check: ensure we are not running against the production DB
    if "core_test" not in db_url:
        pytest.fail(f"Refusing to run tests on non-test DB URL: {db_url}")

    engine = create_async_engine(db_url, echo=False)
    TestSession = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )

    real_repo_root = Path(__file__).parent.parent
    schema_sql_path = real_repo_root / "sql" / "001_consolidated_schema.sql"
    if not schema_sql_path.exists():
        pytest.fail(f"Could not find schema file at {schema_sql_path}")
    schema_sql = schema_sql_path.read_text(encoding="utf-8")

    # Always start from a clean 'core' schema in core_test
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA IF EXISTS core CASCADE;"))
        await conn.execute(text("CREATE SCHEMA core;"))
        for statement in sqlparse.split(schema_sql):
            if statement.strip():
                await conn.execute(text(statement))

    async with TestSession() as session:
        yield session

    # Teardown: only in core_test
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA IF EXISTS core CASCADE;"))

    await engine.dispose()
