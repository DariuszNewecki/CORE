# src/api/v1/development_routes.py
"""
Provides API endpoints for initiating and managing autonomous development cycles.

CONSTITUTIONAL FIX: Uses TaskRepository instead of direct session.add/commit
to comply with db.write_via_governed_cli rule.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from features.autonomy.autonomous_developer import develop_from_goal
from shared.context import CoreContext
from shared.infrastructure.database.session_manager import get_session
from shared.infrastructure.repositories.task_repository import TaskRepository
from will.agents.coder_agent import CoderAgent
from will.agents.execution_agent import _ExecutionAgent
from will.agents.plan_executor import PlanExecutor
from will.orchestration.prompt_pipeline import PromptPipeline


router = APIRouter()


# ID: 7b83814d-b747-4c17-b054-9e8f2b8b8325
class DevelopmentGoal(BaseModel):
    goal: str


@router.post("/develop/goal", status_code=202)
# ID: de19ab6c-6bb6-4d9c-98bd-f1b3783b2188
async def start_development_cycle(
    request: Request,
    payload: DevelopmentGoal,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """
    Accepts a high-level goal, creates a task record, and starts the
    autonomous development cycle in the background.

    CONSTITUTIONAL: Uses TaskRepository for DB writes (db.write_via_governed_cli).
    """
    core_context: CoreContext = request.app.state.core_context

    # Use Repository layer instead of direct session writes
    task_repo = TaskRepository(session)
    new_task = await task_repo.create(
        intent=payload.goal, assigned_role="AutonomousDeveloper", status="planning"
    )

    # FIXED: Create async wrapper that properly passes session to develop_from_goal
    # ID: 419febbe-ce48-49a1-a1a7-ae800ce5cb4a
    async def run_development():
        """Background task that runs autonomous development with proper session management."""
        # Create new session for background task
        async with get_session() as dev_session:
            # Build executor agent (same pattern as CLI command)
            prompt_pipeline = PromptPipeline(core_context.git_service.repo_path)
            plan_executor = PlanExecutor(
                core_context.file_handler,
                core_context.git_service,
                core_context.planner_config,
            )
            coder_agent = CoderAgent(
                cognitive_service=core_context.cognitive_service,
                prompt_pipeline=prompt_pipeline,
                auditor_context=core_context.auditor_context,
            )
            executor_agent = _ExecutionAgent(
                coder_agent=coder_agent,
                plan_executor=plan_executor,
                auditor_context=core_context.auditor_context,
            )

            # Call develop_from_goal with proper DI
            await develop_from_goal(
                session=dev_session,
                context=core_context,
                goal=payload.goal,
                executor_agent=executor_agent,
                task_id=new_task.id,
            )

    background_tasks.add_task(run_development)

    return {"task_id": str(new_task.id), "status": "Task accepted and running."}
