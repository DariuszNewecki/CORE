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
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi import status as http_status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, StringConstraints

from agents.execution_agent import ExecutionAgent
from agents.plan_executor import PlanExecutor
from agents.planner_agent import PlannerAgent
from core.capabilities import introspection
from core.clients import GeneratorClient, OrchestratorClient
from core.errors import register_exception_handlers
from core.file_handler import FileHandler
from core.git_service import GitService
from core.intent_alignment import check_goal_alignment
from core.intent_guard import IntentGuard
from core.prompt_pipeline import PromptPipeline
from shared.config import settings
from shared.logger import configure_logging, getLogger

log = getLogger(__name__)
load_dotenv()

# --- Pydantic v2 string constraints (trim + require non-empty) ---
GoalText = Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]

# simple process-start timestamp for /healthz diagnostics
PROCESS_START_TS = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan handler — runs startup and shutdown logic."""

    # Configure runtime logging once per app start.
    level = os.getenv("CORE_LOG_LEVEL", "INFO")
    json_mode = os.getenv("CORE_LOG_JSON", "false").lower() == "true"
    configure_logging(level=level, json_mode=json_mode)  # logs to sys.__stderr__

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
    app.state.file_handler = FileHandler(str(repo_path))
    app.state.git_service = GitService(str(repo_path))
    app.state.intent_guard = IntentGuard(repo_path)
    app.state.prompt_pipeline = PromptPipeline(repo_path)

    if settings.LLM_ENABLED:
        app.state.orchestrator_client = OrchestratorClient()
        app.state.generator_client = GeneratorClient()
    else:
        app.state.orchestrator_client = None
        app.state.generator_client = None

    log.info("✅ CORE system is online and ready.")
    yield
    log.info("🛑 CORE system shutting down.")


app = FastAPI(lifespan=lifespan)
register_exception_handlers(app)


class GoalRequest(BaseModel):
    """Defines the request body for the /execute_goal endpoint."""

    goal: GoalText


class AlignmentRequest(BaseModel):
    """Request schema for /guard/align."""

    goal: GoalText
    min_coverage: float | None = Field(default=None, ge=0.0, le=1.0)


@app.get("/healthz")
async def healthz():
    """Simple liveness/readiness probe."""
    uptime_s = int(time.time() - PROCESS_START_TS)
    return {"status": "ok", "uptime_seconds": uptime_s}


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


@app.post("/execute_goal")
async def execute_goal(request_data: GoalRequest, request: Request):
    """Execute a high-level goal by planning and generating code."""
    goal = request_data.goal
    log.info("🎯 Received new goal: %r", goal[:200])

    try:
        # 1. Instantiate the PlannerAgent to create the plan
        planner = PlannerAgent(
            orchestrator_client=request.app.state.orchestrator_client,
            prompt_pipeline=request.app.state.prompt_pipeline,
        )
        plan = planner.create_execution_plan(goal)

        # 2. Instantiate the ExecutionAgent to carry out the plan
        plan_executor = PlanExecutor(
            file_handler=request.app.state.file_handler,
            git_service=request.app.state.git_service,
            config=planner.config,  # Use the same config
        )
        execution_agent = ExecutionAgent(
            generator_client=request.app.state.generator_client,
            prompt_pipeline=request.app.state.prompt_pipeline,
            plan_executor=plan_executor,
        )

        # 3. Execute and get the result
        success, message = await execution_agent.execute_plan(goal, plan)

        if success:
            log.info("✅ Goal executed successfully: %s", message)
            return JSONResponse(
                content={"status": "success", "message": message},
                status_code=http_status.HTTP_200_OK,
            )
        else:
            log.error("❌ Goal execution failed: %s", message)
            raise HTTPException(status_code=500, detail=message)

    except Exception as e:
        log.exception("💥 Unexpected error during goal execution")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    """Root endpoint — returns system status."""
    return {"message": "CORE system is online and self-governing."}
