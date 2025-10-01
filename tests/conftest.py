# tests/conftest.py
"""
Central pytest configuration and fixtures for the CORE project.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
import yaml
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from services.database.models import Base
from shared.config import settings


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_fs_with_constitution(tmp_path: Path) -> Path:
    """
    Creates a minimal but valid constitutional file structure in a temporary directory.
    This is the primary fixture for testing services that read from .intent.
    """
    intent_dir = tmp_path / ".intent"
    charter_dir = intent_dir / "charter"
    policies_dir = charter_dir / "policies"
    agent_policies_dir = policies_dir / "agent"
    governance_policies_dir = policies_dir / "governance"
    mind_dir = intent_dir / "mind"
    prompts_dir = mind_dir / "prompts"

    # Create all directories
    for p in [
        agent_policies_dir,
        governance_policies_dir,
        prompts_dir,
    ]:
        p.mkdir(parents=True, exist_ok=True)

    # --- Create Mock Constitutional Files ---

    # meta.yaml
    meta_content = {
        "charter": {
            "policies": {
                "agent": {
                    "micro_proposal_policy": "charter/policies/agent/micro_proposal_policy.yaml",
                    "agent_policy": "charter/policies/agent/agent_policy.yaml",  # ADDED
                },
                "governance": {
                    "available_actions_policy": "charter/policies/governance/available_actions_policy.yaml"
                },
            }
        },
        "mind": {"prompts": {"planner_agent": "mind/prompts/planner_agent.prompt"}},
    }
    (intent_dir / "meta.yaml").write_text(yaml.dump(meta_content))

    # available_actions_policy.yaml
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
            {
                "name": "system.dangerous.execute_shell",
                "description": "A dangerous action.",
                "parameters": [],
            },
        ],
    }
    (governance_policies_dir / "available_actions_policy.yaml").write_text(
        yaml.dump(available_actions_content)
    )

    # micro_proposal_policy.yaml
    micro_proposal_content = {
        "policy_id": "mock-uuid-micro",
        "id": "micro_proposal_policy",
        "version": "1.0.0",
        "title": "Mock Micro Proposal",
        "purpose": "...",
        "status": "active",
        "owners": {"primary": "test"},
        "review": {"frequency": "annual"},
        "rules": [
            {
                "id": "safe_actions",
                "description": "...",
                "enforcement": "error",
                "allowed_actions": ["autonomy.self_healing.format_code"],
            },
            {
                "id": "safe_paths",
                "description": "...",
                "enforcement": "error",
                "allowed_paths": ["src/safe_dir/*"],
                "forbidden_paths": [".intent/**"],
            },
        ],
    }
    (agent_policies_dir / "micro_proposal_policy.yaml").write_text(
        yaml.dump(micro_proposal_content)
    )

    # agent_policy.yaml (NEWLY ADDED)
    agent_policy_content = {
        "policy_id": "mock-uuid-agent",
        "id": "agent_policy",
        "version": "1.0.0",
        "title": "Mock Agent Policy",
        "purpose": "...",
        "status": "active",
        "owners": {"primary": "test"},
        "review": {"frequency": "annual"},
        "rules": [],
        "execution_agent": {"max_correction_attempts": 2},
    }
    (agent_policies_dir / "agent_policy.yaml").write_text(
        yaml.dump(agent_policy_content)
    )

    # planner_agent.prompt
    (prompts_dir / "planner_agent.prompt").write_text("Plan for: {goal}")

    return tmp_path


@pytest.fixture
def mock_core_env(mock_fs_with_constitution: Path, monkeypatch) -> Path:
    """
    A comprehensive fixture that sets up the file system and patches the
    global `settings` object to point to the temporary environment.
    """
    monkeypatch.setattr(settings, "REPO_PATH", mock_fs_with_constitution)
    settings.initialize_for_test(mock_fs_with_constitution)
    return mock_fs_with_constitution


@pytest.fixture(scope="function")
async def get_test_session(monkeypatch) -> AsyncSession:
    """
    Provides an in-memory SQLite database session for testing.
    - Wipes and recreates the DB for each test function for isolation.
    - Patches the DATABASE_URL setting to point to the in-memory DB.
    """
    db_url = "sqlite+aiosqlite:///:memory:"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setattr(settings, "DATABASE_URL", db_url)

    engine = create_async_engine(db_url, echo=False)
    TestSession = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSession() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()
