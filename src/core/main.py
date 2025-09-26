# src/core/main.py
"""
Provides the FastAPI-based API gateway and execution engine for the CORE system's goal processing and system integration.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi import status as http_status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from core.cognitive_service import CognitiveService
from core.errors import register_exception_handlers
from core.intent_alignment import check_goal_alignment
from core.knowledge_service import KnowledgeService
from services.clients.qdrant_client import QdrantService
from shared.config import settings
from shared.logger import getLogger

log = getLogger(__name__)
load_dotenv()


@asynccontextmanager
# ID: f453301d-951e-4a0e-8f21-1048e361840d
async def lifespan(app: FastAPI):
    """FastAPI lifespan handler — runs startup and shutdown logic."""
    log.info("🚀 Starting CORE system...")

    log.info("🛠️  Initializing shared services...")
    repo_path = Path(".")

    knowledge_service = KnowledgeService(repo_path)
    await knowledge_service.get_graph()

    app.state.knowledge_service = knowledge_service
    app.state.cognitive_service = CognitiveService(repo_path)
    app.state.qdrant_service = QdrantService()

    if not settings.LLM_ENABLED:
        log.warning(
            "⚠️ LLMs are disabled. The 'execute_goal' endpoint will not be functional."
        )

    log.info("✅ CORE system is online and ready.")
    yield
    log.info("🛑 CORE system shutting down.")


app = FastAPI(lifespan=lifespan)
register_exception_handlers(app)


# ID: f1f7835a-faf3-4ce4-9953-314053c4e07d
class GoalRequest(BaseModel):
    """Defines the request body for the /execute_goal endpoint."""

    goal: str = Field(min_length=1, json_schema_extra={"strip_whitespace": True})


# ID: 830bec8a-4a90-4b37-b38c-af4ad39180b0
class AlignmentRequest(BaseModel):
    """Request schema for /guard/align."""

    goal: str = Field(min_length=1, json_schema_extra={"strip_whitespace": True})
    min_coverage: float | None = Field(default=None, ge=0.0, le=1.0)


@app.post("/guard/align")
# ID: 16de5543-e473-492d-a09d-2ee4927e944e
async def guard_align(payload: AlignmentRequest):
    """Evaluate a goal against the NorthStar and optional blocklist."""
    ok, details = check_goal_alignment(payload.goal, Path("."))
    if payload.min_coverage is not None:
        cov = details.get("coverage")
        if cov is None or cov < payload.min_coverage:
            ok = False
            if "low_mission_overlap" not in details["violations"]:
                details["violations"].append("low_mission_overlap")
    status = "ok" if ok else "rejected"
    return JSONResponse(
        {"status": status, "details": details}, status_code=http_status.HTTP_200_OK
    )


@app.get("/knowledge/capabilities")
# ID: 3f1cfcdc-1f47-421c-b166-cbfda59eeed3
async def list_capabilities(request: Request):
    """Returns a list of all capabilities the system has declared."""
    knowledge_service: KnowledgeService = request.app.state.knowledge_service
    capabilities = await knowledge_service.list_capabilities()
    return {"capabilities": capabilities}


@app.post("/execute_goal")
# ID: f98b4887-03b3-4e90-8016-93cda8dc2a81
async def execute_goal(request_data: GoalRequest, request: Request):
    """
    Execute a high-level goal by planning and generating code.
    """
    from core.agents.execution_agent import ExecutionAgent
    from core.agents.plan_executor import PlanExecutor
    from core.agents.planner_agent import PlannerAgent
    from core.agents.reconnaissance_agent import ReconnaissanceAgent
    from core.file_handler import FileHandler
    from core.git_service import GitService
    from core.prompt_pipeline import PromptPipeline
    from features.governance.audit_context import AuditorContext
    from shared.models import PlanExecutionError, PlannerConfig

    goal = request_data.goal
    log.info("🎯 Received new goal via API: %r", goal[:200])

    if not settings.LLM_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="LLM capabilities are disabled in the current environment configuration.",
        )

    try:
        repo_path = Path(".")
        auditor_context = AuditorContext(repo_path)
        await auditor_context.load_knowledge_graph()  # Ensure context is loaded

        git_service = GitService(repo_path=str(repo_path))
        cognitive_service: CognitiveService = request.app.state.cognitive_service
        knowledge_service: KnowledgeService = request.app.state.knowledge_service
        file_handler = FileHandler(repo_path=str(repo_path))
        prompt_pipeline = PromptPipeline(repo_path=repo_path)
        planner_config = PlannerConfig()
        plan_executor = PlanExecutor(file_handler, git_service, planner_config)

        graph = await knowledge_service.get_graph()
        recon_agent = ReconnaissanceAgent(graph)
        context_report = recon_agent.generate_report(goal)
        log.info(f"   -> Generated Surgical Context Report:\n{context_report}")

        planner = PlannerAgent(cognitive_service)
        plan = planner.create_execution_plan(goal)
        if not plan:
            raise PlanExecutionError("Planner failed to create a valid execution plan.")

        executor = ExecutionAgent(
            cognitive_service, prompt_pipeline, plan_executor, auditor_context
        )
        success, message = await executor.execute_plan(high_level_goal=goal, plan=plan)

        if success:
            return JSONResponse(
                content={"status": "success", "message": message},
                status_code=http_status.HTTP_200_OK,
            )
        else:
            raise HTTPException(status_code=500, detail=message)

    except PlanExecutionError as e:
        raise HTTPException(status_code=400, detail=f"Planning Error: {e}")
    except Exception as e:
        log.error(f"💥 Unexpected error during goal execution: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {e}"
        )


@app.get("/")
# ID: 2fe70272-eba7-4666-9d31-2dba9c2c6851
async def root():
    """Root endpoint — returns system status."""
    return {"message": "CORE system is online and self-governing."}
