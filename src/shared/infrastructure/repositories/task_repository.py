# src/shared/infrastructure/repositories/task_repository.py
"""
Repository for Task entity - enforces db.write_via_governed_cli constitutional rule.
All database writes for tasks must go through this repository.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infrastructure.database.models import Task
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: template_value
# ID: 2c2de8fa-dddf-43db-ae01-37cb457b674d
class TaskRepository:
    """Repository pattern for Task entity - constitutional DB access layer."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ID: 60c5391c-73ae-4a21-a6b3-458d3ce467c7
    async def create(
        self, intent: str, assigned_role: str, status: str = "planning"
    ) -> Task:
        """
        Create a new task with constitutional governance.

        Returns the created task with ID populated.
        """
        new_task = Task(intent=intent, assigned_role=assigned_role, status=status)
        self.session.add(new_task)
        await self.session.commit()
        await self.session.refresh(new_task)

        logger.info("Created task %s with role %s", new_task.id, assigned_role)
        return new_task

    # ID: f325f7e6-51b5-4248-a1de-3073c7e9154a
    async def get_by_id(self, task_id: UUID) -> Task | None:
        """Retrieve a task by ID."""
        result = await self.session.execute(select(Task).where(Task.id == task_id))
        return result.scalar_one_or_none()

    # ID: 4571c652-06df-4e4b-8cbe-364afd9c5f42
    async def update_status(self, task_id: UUID, status: str) -> Task | None:
        """Update task status."""
        task = await self.get_by_id(task_id)
        if task:
            task.status = status
            await self.session.commit()
            await self.session.refresh(task)
        return task
