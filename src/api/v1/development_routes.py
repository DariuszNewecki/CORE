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
from shared.infrastructure.database.session_manager import get_db_session
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
    session: AsyncSession = Depends(get_db_session),
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

    background_tasks.add_task(
        develop_from_goal, core_context, payload.goal, task_id=new_task.id
    )

    return {"task_id": str(new_task.id), "status": "Task accepted and running."}
