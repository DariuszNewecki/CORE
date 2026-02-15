# src/api/v1/development_routes.py
# ID: 7d485ce8-8356-40c7-8272-9a05f58cf89d
"""
Provides API endpoints for initiating and managing autonomous development cycles.

UPDATED (Phase 5): Removed _ExecutionAgent dependency.
Now uses develop_from_goal which internally uses the new UNIX-compliant pattern.

CONSTITUTIONAL FIX: Uses service_registry.session() instead of direct get_session
to comply with architecture.api.no_direct_database_access rule.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from body.autonomy.autonomous_developer import develop_from_goal
from body.services.service_registry import service_registry
from shared.context import CoreContext
from shared.infrastructure.repositories.task_repository import TaskRepository


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
    session: AsyncSession = Depends(service_registry.session),
):
    """
    Accepts a high-level goal, creates a task record, and starts the
    autonomous development cycle in the background.

    UPDATED: No longer needs to build executor_agent - develop_from_goal
    handles all agent orchestration internally using UNIX-compliant pattern.

    CONSTITUTIONAL: Uses TaskRepository for DB writes and service_registry
    for session access (Mind-Body-Will separation).
    """
    core_context: CoreContext = request.app.state.core_context

    # Use Repository layer instead of direct session writes
    task_repo = TaskRepository(session)
    new_task = await task_repo.create(
        intent=payload.goal, assigned_role="AutonomousDeveloper", status="planning"
    )

    # ID: 419febbe-ce48-49a1-a1a7-ae800ce5cb4a
    async def run_development():
        """
        Background task that runs autonomous development.

        UPDATED: Simplified! No need to build agents manually.
        develop_from_goal now handles all orchestration internally.

        CONSTITUTIONAL: Uses service_registry.session() for background task.
        """
        # Create new session for background task via service registry
        async with service_registry.session() as dev_session:
            # Just call develop_from_goal!
            # It builds all agents internally using UNIX-compliant pattern
            await develop_from_goal(
                session=dev_session,
                context=core_context,
                goal=payload.goal,
                task_id=new_task.id,
                output_mode="direct",
            )

    background_tasks.add_task(run_development)

    return {"task_id": str(new_task.id), "status": "Task accepted and running."}
