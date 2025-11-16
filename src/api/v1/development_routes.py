# src/api/v1/development_routes.py
"""
Provides API endpoints for initiating and managing autonomous development cycles.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from features.autonomy.autonomous_developer import develop_from_goal
from pydantic import BaseModel
from services.database.models import Task
from services.database.session_manager import get_db_session
from shared.context import CoreContext
from sqlalchemy.ext.asyncio import AsyncSession

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
    session: AsyncSession = Depends(get_db_session),
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

    background_tasks.add_task(
        develop_from_goal, core_context, payload.goal, task_id=new_task.id
    )

    return {"task_id": str(new_task.id), "status": "Task accepted and running."}
