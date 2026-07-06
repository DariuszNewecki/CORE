# tests/helpers/fixtures.py
"""
Shared test fixtures for CORE's test suite.

Provides lightweight, reusable mock construction helpers so individual test
modules don't have to duplicate boilerplate. All mocks use unittest.mock;
no DB, LLM, or Qdrant connections are established here.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock


# ID: d9a8273f-95dc-42ec-822d-e396b52f078f
def create_mock_context(
    *,
    repo_path: str | Path = "/opt/dev/CORE",
    cognitive_service: object | None = None,
    qdrant_service: object | None = None,
) -> MagicMock:
    """Return a MagicMock shaped like CoreContext for unit tests.

    Mandatory services (git_service, knowledge_service, file_handler,
    file_service) are pre-populated with sensible mocks so callers don't
    have to set them up individually.  Genuinely-optional services
    (cognitive_service, qdrant_service) default to None — callers pass
    a mock when the code-under-test actually exercises those paths.
    """
    ctx = MagicMock(name="CoreContext")

    # git_service — most tests just need repo_path
    ctx.git_service = MagicMock(name="GitService")
    ctx.git_service.repo_path = str(repo_path)

    # knowledge_service
    ctx.knowledge_service = MagicMock(name="KnowledgeService")

    # file_handler / file_service
    ctx.file_handler = MagicMock(name="FileHandler")
    ctx.file_service = MagicMock(name="FileService")

    # Registry — async get_* helpers used by Will-layer warm-up
    ctx.registry = MagicMock(name="ServiceRegistry")
    ctx.registry.get_cognitive_service = AsyncMock(return_value=cognitive_service)
    ctx.registry.get_qdrant_service = AsyncMock(return_value=qdrant_service)
    ctx.registry.session = MagicMock(name="SessionFactory")

    # Genuinely optional services (ADR-128)
    ctx.cognitive_service = cognitive_service
    ctx.qdrant_service = qdrant_service
    ctx.auditor_context = None
    ctx.planner_config = None

    # Infrastructure set post-construction
    ctx.path_resolver = MagicMock(name="PathResolver")
    ctx.action_executor = None

    ctx._is_test_mode = True
    ctx.debug = False
    ctx.verbose = False
    ctx.file_content_cache = {}

    return ctx
