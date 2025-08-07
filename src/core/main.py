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
from typing import Dict
from fastapi import FastAPI, HTTPException, Request, status as http_status
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from dotenv import load_dotenv
# --- FIX: Import Pydantic's BaseModel for request modeling ---
from pydantic import BaseModel

# Local imports
from core.clients import OrchestratorClient, GeneratorClient
from core.file_handler import FileHandler
from core.git_service import GitService
from core.intent_guard import IntentGuard
from agents.planner_agent import PlannerAgent
from core.capabilities import introspection
from shared.logger import getLogger

# --- Global Setup ---
log = getLogger(__name__)
load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan handler — runs startup and shutdown logic."""
    log.info("🚀 Starting CORE system...")
    
    log.info("🧠 Performing startup introspection...")
    if not introspection():
        log.warning("⚠️ Introspection cycle completed with errors. System may be unstable.")
    else:
        log.info("✅ Introspection complete. System state is constitutionally valid.")
    
    # Initialize services and store them in the app state
    log.info("🛠️  Initializing services...")
    app.state.orchestrator_client = OrchestratorClient()
    app.state.generator_client = GeneratorClient()
    app.state.file_handler = FileHandler(".")
    app.state.git_service = GitService(".")
    app.state.intent_guard = IntentGuard(".")
    log.info("🤖 Initializing PlannerAgent...")
    app.state.planner = PlannerAgent(
        orchestrator_client=app.state.orchestrator_client,
        generator_client=app.state.generator_client,
        file_handler=app.state.file_handler,
        git_service=app.state.git_service,
        intent_guard=app.state.intent_guard
    )
    log.info("✅ CORE system is online and ready.")
    yield
    log.info("🛑 CORE system shutting down.")

# Initialize FastAPI app with the lifespan event handler
app = FastAPI(lifespan=lifespan)

# --- FIX: Define a Pydantic model for the request body ---
# This enables automatic validation and API documentation for the endpoint.
class GoalRequest(BaseModel):
    goal: str

@app.post("/execute_goal")
async def execute_goal(request_data: GoalRequest, request: Request):
    """Execute a high-level goal by planning and generating code."""
    # --- FIX: Use the validated Pydantic model directly ---
    # FastAPI handles the validation. If 'goal' is missing or not a string,
    # it will automatically return a 422 Unprocessable Entity error.
    goal = request_data.goal

    log.info(f"🎯 Received new goal: '{goal}'")
    try:
        planner: PlannerAgent = request.app.state.planner
        plan = planner.create_execution_plan(goal)
        
        success, message = await planner.execute_plan(plan)
        
        if success:
            log.info(f"✅ Goal executed successfully. Message: {message}")
            return JSONResponse(
                content={"status": "success", "message": message},
                status_code=http_status.HTTP_200_OK
            )
        else:
            log.error(f"❌ Goal execution failed. Reason: {message}")
            raise HTTPException(status_code=500, detail=f"Goal execution failed: {message}")

    except Exception as e:
        log.error(f"💥 An unexpected error occurred during goal execution: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@app.get("/")
async def root():
    """Root endpoint — returns system status."""
    return {"message": "CORE system is online and self-governing."}