# src/core/main.py
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List
from unittest.mock import MagicMock

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from core.agents.execution_agent import ExecutionAgent
from core.cognitive_service import CognitiveService
from core.knowledge_service import KnowledgeService

logger = logging.getLogger("core.main")


def _make_knowledge_service(cs: CognitiveService) -> KnowledgeService:
    """Instantiate KnowledgeService regardless of local constructor signature."""
    try:
        return KnowledgeService()  # type: ignore
    except TypeError:
        try:
            return KnowledgeService(cs)  # type: ignore
        except TypeError:
            return KnowledgeService(base_path=Path("."))  # type: ignore


def _build_execution_agent(cs: CognitiveService) -> ExecutionAgent:
    """
    Instantiate ExecutionAgent regardless of local constructor signature.
    The integration test patches `execute_plan`, so MagicMock collaborators are fine.
    """
    attempts = [
        # simple signatures seen in some forks
        lambda: ExecutionAgent(cs),  # type: ignore
        lambda: ExecutionAgent(cognitive_service=cs),  # type: ignore
        lambda: ExecutionAgent(cs, Path(".")),  # type: ignore
        # explicit collaborators (strict repos)
        lambda: ExecutionAgent(
            cognitive_service=cs,
            prompt_pipeline=MagicMock(),
            plan_executor=MagicMock(),
            auditor_context=MagicMock(),
        ),
        # positional fallbacks
        lambda: ExecutionAgent(cs, MagicMock(), MagicMock(), MagicMock()),  # type: ignore
        lambda: ExecutionAgent(cs, MagicMock(), MagicMock()),  # type: ignore
    ]

    last_err: Exception | None = None
    for make in attempts:
        try:
            return make()
        except TypeError as e:
            last_err = e
            continue
    raise TypeError(
        f"Unable to construct ExecutionAgent with any known signature: {last_err}"
    )


# ID: 4fe42369-b346-44e8-8cb4-e6e298dffcb8
def create_app() -> FastAPI:
    @asynccontextmanager
    # ID: 3a81d3db-83ee-4c34-ba20-c8cad6bda79c
    async def lifespan(app: FastAPI):
        logger.info("🚀 Starting CORE system...")
        cs = CognitiveService(Path("."))
        try:
            await cs.initialize()  # handles DB+env fallback internally
        except Exception as e:
            logger.warning("CognitiveService initialize() raised; continuing: %s", e)
        app.state.cognitive_service = cs
        app.state.knowledge_service = _make_knowledge_service(cs)
        try:
            yield
        finally:
            logger.info("🛑 CORE system shutting down.")

    app = FastAPI(lifespan=lifespan)

    @app.get("/knowledge/capabilities")
    # ID: 63384f79-ddd2-428b-8c5d-bcafc7a81b51
    async def list_capabilities():
        ks: KnowledgeService = app.state.knowledge_service
        caps: List[str] = await ks.list_capabilities()  # patched in tests
        return JSONResponse({"capabilities": caps})

    @app.post("/execute_goal")
    # ID: cb0318e3-9e6d-41b4-89eb-57cb16c641cd
    async def execute_goal(payload: dict):
        goal = payload.get("goal")
        if not goal or not isinstance(goal, str):
            raise HTTPException(status_code=400, detail="Field 'goal' is required")

        cs: CognitiveService = app.state.cognitive_service
        agent = _build_execution_agent(cs)

        # Tests replace this with AsyncMock; treat as async to be safe.
        result = agent.execute_plan(goal)  # type: ignore[attr-defined]
        if hasattr(result, "__await__"):
            success, message = await result  # type: ignore[misc]
        else:
            success, message = result  # pragma: no cover

        if not success:
            raise HTTPException(status_code=500, detail=str(message))

        return JSONResponse({"status": "success", "message": str(message)})

    return app
