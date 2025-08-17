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

from agents.planner_agent import PlannerAgent
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi import status as http_status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from shared.config import settings
from shared.logger import getLogger

from core.capabilities import introspection
from core.clients import GeneratorClient, OrchestratorClient
from core.errors import register_exception_handlers
from core.file_handler import FileHandler
from core.git_service import GitService
from core.intent_alignment import check_goal_alignment
from core.intent_guard import IntentGuard

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

    # Initialize services that are safe to be singletons and store them in the app state
    log.info("🛠️  Initializing shared services...")
    if settings.LLM_ENABLED:
        app.state.orchestrator_client = OrchestratorClient()
        app.state.generator_client = GeneratorClient()
    else:
        log.info("⚙️  LLM_ENABLED=false — skipping LLM client initialization.")
        app.state.orchestrator_client = None
        app.state.generator_client = None

    app.state.git_service = GitService(".")
    app.state.intent_guard = IntentGuard(Path("."))

    log.info("✅ CORE system is online and ready.")
    yield
    log.info("🛑 CORE system shutting down.")


app = FastAPI(lifespan=lifespan)
register_exception_handlers(app)


class GoalRequest(BaseModel):
    """Defines the request body for the /execute_goal endpoint."""

    goal: str = Field(min_length=1, strip_whitespace=True)


class AlignmentRequest(BaseModel):
    """Request schema for /guard/align."""

    goal: str = Field(min_length=1, strip_whitespace=True)
    min_coverage: float | None = Field(default=None, ge=0.0, le=1.0)


@app.post("/guard/align")
async def guard_align(payload: AlignmentRequest):
    """Evaluate a goal against the NorthStar and optional blocklist.

    Returns {"status": "ok"|"rejected", "details": {...}} with short reason codes.
    """
    ok, details = check_goal_alignment(payload.goal, Path("."))

    # Optional threshold enforcement (client-provided)
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


@app.post("/execute_goal")
async def execute_goal(request_data: GoalRequest, request: Request):
    """Execute a high-level goal by planning and generating code."""
    goal = request_data.goal
    # Avoid logging excessively long/sensitive payloads
    log.info("🎯 Received new goal: %r", goal[:200])

    try:
        file_handler = FileHandler(".")
        planner = PlannerAgent(
            orchestrator_client=request.app.state.orchestrator_client,
            generator_client=request.app.state.generator_client,
            file_handler=file_handler,
            git_service=request.app.state.git_service,
            intent_guard=request.app.state.intent_guard,
        )

        success, message = await planner.execute_plan(goal)

        if success:
            log.info("✅ Goal executed successfully: %s", message)
            return JSONResponse(
                content={"status": "success", "message": message},
                status_code=http_status.HTTP_200_OK,
            )
        else:
            # Log full details server-side; return generic failure to client (CWE-209 safe)
            log.error("❌ Goal execution failed: %s", message)
            raise HTTPException(status_code=500)

    except Exception:
        # Capture traceback in logs, but return generic error to client (handled by global handler)
        log.exception("💥 Unexpected error during goal execution")
        raise HTTPException(status_code=500)


@app.get("/")
async def root():
    """Root endpoint — returns system status."""
    return {"message": "CORE system is online and self-governing."}
