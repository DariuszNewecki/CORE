# src/api/v1/development_routes.py

"""
Development API endpoints.

CONSTITUTIONAL FIX (architecture.api.no_direct_database_access):
All session access now routes through api.dependencies — the single
sanctioned provider. Zero direct imports from shared.infrastructure
in this file.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_api_session, open_background_session
from shared.context import CoreContext
from shared.infrastructure.repositories.task_repository import TaskRepository
from will.autonomy.autonomous_developer import develop_from_goal


router = APIRouter()


# ID: 7b83814d-b747-4c17-b054-9e8f2b8b8325
class DevelopmentGoal(BaseModel):
    """
        DevelopmentGoal is a Pydantic BaseModel with a single string attribute for a development goal.
    Args: None
    Returns: None
    """

    """
    This Python class defines a DevelopmentGoal with an attribute for the development goal as a string, inheriting from BaseModel.
    """

    """
    This class defines a DevelopmentGoal with a single attribute goal of type str, inheriting from BaseModel.
    """

    """
    This class defines a DevelopmentGoal with a single attribute for the development goal as a string, inheriting from BaseModel.
    """

    """
    This class defines a DevelopmentGoal with a single attribute for the development goal as a string, inheriting from BaseModel.
    """

    """
    This class represents a development goal as a string, inheriting from BaseModel.
    """

    goal: str


@router.post("/develop/goal", status_code=202)
# ID: de19ab6c-6bb6-4d9c-98bd-f1b3783b2188
async def start_development_cycle(
    request: Request,
    payload: DevelopmentGoal,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_api_session),
) -> dict:
    """
        Starts a development cycle by accepting a development goal, creating a task record, and scheduling it for background processing.
    Args: request: the HTTP request, payload: the development goal, background_tasks: for scheduling background work, session: the database session.
    Returns: a dictionary.
    """
    """
    Starts a development cycle by accepting a development goal, creating a task record, and scheduling it for background processing.
    """
    """
        One sentence summary:
    Starts a development cycle by accepting a development goal, creating a task record, and scheduling it for background processing.
    """
    """
    Starts a development cycle by accepting a goal, creating a task record, and scheduling it for background processing.
    """
    """
        One sentence summary:
    Starts a development cycle by accepting a goal, creating a task record, and scheduling it for background processing.
    """
    """
        Starts a development cycle by accepting a high-level goal, creating a task record, and scheduling it for background processing.

    Args:
    - request (Request): The HTTP request object.
    - payload (DevelopmentGoal): The goal data.
    - background_tasks (BackgroundTasks): For handling asynchronous tasks.
    - session (AsyncSession, optional): The database session. Defaults to the API session.

    Returns:
    - dict: A response indicating success or failure of task creation.
    """
    """
    Accepts a high-level goal, creates a task record, and starts the
    autonomous development cycle in the background.

    CONSTITUTIONAL: TaskRepository for DB writes, api.dependencies for
    session access. No Body or shared.infrastructure imports.
    """
    core_context: CoreContext = request.app.state.core_context

    task_repo = TaskRepository(session)
    new_task = await task_repo.create(
        intent=payload.goal, assigned_role="AutonomousDeveloper", status="planning"
    )

    # ID: 419febbe-ce48-49a1-a1a7-ae800ce5cb4a
    async def run_development() -> None:
        """Background task — session acquired via sanctioned provider."""
        async with open_background_session() as dev_session:
            await develop_from_goal(
                session=dev_session,
                context=core_context,
                goal=payload.goal,
                task_id=new_task.id,
                output_mode="direct",
            )

    background_tasks.add_task(run_development)
    return {"task_id": str(new_task.id), "status": "Task accepted and running."}
