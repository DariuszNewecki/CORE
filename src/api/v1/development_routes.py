# src/api/v1/development_routes.py
"""
Provides API endpoints for initiating and managing autonomous development cycles.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from features.autonomy.autonomous_developer import develop_from_goal
from pydantic import BaseModel
from services.database.models import Task
from services.database.session_manager import get_session
from shared.context import CoreContext
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


# ID: 6e66ab0d-60fb-4393-b87c-2a65f0f1a8d3
class DevelopmentGoal(BaseModel):
    goal: str


@router.post("/develop/goal", status_code=202)
# ID: dac80f82-1aae-4dc1-9f6a-b9eb8e08686e
async def start_development_cycle(
    request: Request,
    payload: DevelopmentGoal,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """
    Accepts a high-level goal, creates a task record, and starts the
    autonomous development cycle in the background.
    """
    core_context: CoreContext = request.app.state.core_context

    new_task = Task(
        intent=payload.goal, assigned_role="AutonomousDeveloper", status="planning"
    )
    session.add(new_task)
    await session.commit()
    await session.refresh(new_task)

    # Pass the task_id to the background task for status updates
    background_tasks.add_task(
        develop_from_goal, core_context, payload.goal, task_id=new_task.id
    )

    return {"task_id": str(new_task.id), "status": "Task accepted and running."}
