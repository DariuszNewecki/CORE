# src/core/main.py
"""
main.py — CORE's API Gateway and Execution Engine

Implements the FastAPI server that handles:
- Goal submission
- Write confirmation
- Test execution
- System status

Integrates all core capabilities into a unified interface.
"""
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi import status as http_status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# --- REFACTORED IMPORT ---
# We now import the single function that runs the whole cycle.
from agents.development_cycle import run_development_cycle
from core.capabilities import introspection
from core.cognitive_service import CognitiveService  # <-- ADD THIS IMPORT
from core.errors import register_exception_handlers
from core.intent_alignment import (
    check_goal_alignment,
)  # This is needed for /guard/align
from core.knowledge_service import KnowledgeService
from shared.config import settings
from shared.logger import getLogger

log = getLogger(__name__)
load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan handler — runs startup and shutdown logic."""
    log.info("🚀 Starting CORE system...")

    log.info("🧠 Performing startup introspection...")
    if not introspection():
        log.warning(
            "⚠️ Introspection cycle completed with errors. System may be unstable."
        )
    else:
        log.info("✅ Introspection complete. System state is constitutionally valid.")

    log.info("🛠️  Initializing shared services...")
    repo_path = Path(".")
    app.state.knowledge_service = KnowledgeService(repo_path)
    app.state.cognitive_service = CognitiveService(repo_path)  # <-- ADD THIS LINE

    if not settings.LLM_ENABLED:
        log.warning(
            "⚠️ LLMs are disabled. The 'execute_goal' endpoint will not be functional."
        )

    log.info("✅ CORE system is online and ready.")
    yield
    log.info("🛑 CORE system shutting down.")


app = FastAPI(lifespan=lifespan)
register_exception_handlers(app)


class GoalRequest(BaseModel):
    """Defines the request body for the /execute_goal endpoint."""

    goal: str = Field(min_length=1, strip_whitespace=True)


# --- THIS SECTION IS PRESERVED FROM YOUR ORIGINAL FILE ---
class AlignmentRequest(BaseModel):
    """Request schema for /guard/align."""

    goal: str = Field(min_length=1, strip_whitespace=True)
    min_coverage: float | None = Field(default=None, ge=0.0, le=1.0)


@app.post("/guard/align")
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


# --- END OF PRESERVED SECTION ---


@app.get("/knowledge/capabilities")
async def list_capabilities(request: Request):
    """Returns a list of all capabilities the system has declared."""
    knowledge_service: KnowledgeService = request.app.state.knowledge_service
    return {"capabilities": knowledge_service.list_capabilities()}


@app.post("/execute_goal")
async def execute_goal(request_data: GoalRequest):
    """
    Execute a high-level goal by planning and generating code.
    This endpoint is a simple wrapper around the core development cycle logic.
    """
    goal = request_data.goal
    log.info("🎯 Received new goal via API: %r", goal[:200])

    if not settings.LLM_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="LLM capabilities are disabled in the current environment configuration.",
        )

    # --- THIS IS THE REFACTORED LOGIC ---
    # The endpoint now makes a single, clean call to our reusable function.
    success, message = await run_development_cycle(goal)

    if success:
        log.info("✅ Goal executed successfully: %s", message)
        return JSONResponse(
            content={"status": "success", "message": message},
            status_code=http_status.HTTP_200_OK,
        )
    else:
        log.error("❌ Goal execution failed: %s", message)
        raise HTTPException(status_code=500, detail=message)


@app.get("/")
async def root():
    """Root endpoint — returns system status."""
    return {"message": "CORE system is online and self-governing."}