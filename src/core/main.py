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

# Local imports (now that 'src' is on the pythonpath for tests)
from core.clients import OrchestratorClient, GeneratorClient
from core.file_handler import FileHandler
from core.git_service import GitService
from core.intent_guard import IntentGuard
from agents.planner_agent import PlannerAgent
from core.capabilities import introspection # Import introspection

# Load environment variables from .env file
load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan handler — runs startup and shutdown logic."""
    print("🚀 Starting CORE system...")
    
    # Run introspection on startup to ensure knowledge graph is up-to-date
    introspection() 
    print("🔍 Introspection complete.")
    
    # Initialize services and store them in the app state
    app.state.orchestrator_client = OrchestratorClient()
    app.state.generator_client = GeneratorClient()
    app.state.file_handler = FileHandler(".")
    app.state.git_service = GitService(".")
    app.state.intent_guard = IntentGuard(".")
    
    app.state.planner = PlannerAgent(
        orchestrator_client=app.state.orchestrator_client,
        generator_client=app.state.generator_client,
        file_handler=app.state.file_handler,
        git_service=app.state.git_service,
        intent_guard=app.state.intent_guard
    )
    print("✅ CORE system initialized.")
    yield
    print("🛑 CORE system shutting down.")

# Initialize FastAPI app with the lifespan event handler
app = FastAPI(lifespan=lifespan)

@app.post("/execute_goal")
async def execute_goal(request_data: Dict[str, str], request: Request):
    """Execute a high-level goal by planning and generating code."""
    goal = request_data.get("goal")
    if not goal:
        raise HTTPException(status_code=400, detail="Missing 'goal' in request.")

    try:
        planner: PlannerAgent = request.app.state.planner
        plan = planner.create_execution_plan(goal)
        
        success, message = await planner.execute_plan(plan)
        
        if success:
            return JSONResponse(
                content={"status": "success", "message": message},
                status_code=http_status.HTTP_200_OK
            )
        else:
            raise HTTPException(status_code=500, detail=f"Goal execution failed: {message}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@app.get("/")
async def root():
    """Root endpoint — returns system status."""
    return {"message": "CORE system is online and self-governing."}