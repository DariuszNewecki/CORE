# src/shared/infrastructure/repositories/decision_trace_repository.py
# ID: repository.decision_trace
"""
DecisionTrace Repository - Governed database access for decision traces.

Constitutional Compliance:
- db.write_via_governed_cli: All writes go through repository layer
- separation_of_concerns: Repository handles DB, not business logic
- single_responsibility: Only decision trace CRUD operations
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infrastructure.database.models.decision_traces import DecisionTrace
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 8d9e0f1a-2b3c-4d5e-6f7a-8b9c0d1e2f3a
class DecisionTraceRepository:
    """
    Repository for decision trace database operations.

    Follows CORE's repository pattern:
    - No direct session.add/commit in calling code
    - Centralized query logic
    - Type-safe operations
    - Proper error handling
    """

    def __init__(self, session: AsyncSession):
        """Initialize repository with database session."""
        self.session = session

    # ID: 9e0f1a2b-3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d
    # ID: f1746e04-8e4f-4ea9-9678-948ff69793d1
    async def create(
        self,
        session_id: str,
        agent_name: str,
        decisions: list[dict[str, Any]],
        goal: str | None = None,
        pattern_stats: dict[str, int] | None = None,
        has_violations: bool | None = None,
        violation_count: int | None = None,
        duration_ms: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DecisionTrace:
        """
        Create a new decision trace record.

        Args:
            session_id: Unique session identifier
            agent_name: Name of agent making decisions
            decisions: List of decision dictionaries
            goal: Optional high-level goal
            pattern_stats: Optional pattern frequency map
            has_violations: Optional violation flag
            violation_count: Optional violation count
            duration_ms: Optional session duration
            metadata: Optional additional metadata

        Returns:
            Created DecisionTrace instance
        """
        trace = DecisionTrace(
            session_id=session_id,
            agent_name=agent_name,
            goal=goal,
            decisions=decisions,  # SQLAlchemy handles list->JSONB
            decision_count=len(decisions),
            pattern_stats=pattern_stats,
            has_violations=(
                str(has_violations).lower() if has_violations is not None else None
            ),
            violation_count=violation_count,
            duration_ms=duration_ms,
            extra_metadata=metadata
            or {},  # FIXED: Map to model column name 'extra_metadata'
        )

        self.session.add(trace)
        await self.session.flush()  # Get ID without committing

        logger.debug(
            "Created decision trace: session=%s agent=%s decisions=%d",
            session_id,
            agent_name,
            len(decisions),
        )

        return trace

    # ID: 0f1a2b3c-4d5e-6f7a-8b9c-0d1e2f3a4b5c
    async def get_by_session_id(self, session_id: str) -> DecisionTrace | None:
        """
        Retrieve decision trace by session ID.

        FIXED: If multiple snapshots exist, returns the most recent one
        (highest decision count) to prevent MultipleResultsFound error.
        """
        stmt = (
            select(DecisionTrace)
            .where(DecisionTrace.session_id == session_id)
            .order_by(desc(DecisionTrace.decision_count))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    # ID: 1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d
    async def get_recent(
        self,
        limit: int = 10,
        agent_name: str | None = None,
        failures_only: bool = False,
    ) -> list[DecisionTrace]:
        """
        Get recent decision traces with optional filtering.

        Args:
            limit: Maximum number of traces to return
            agent_name: Optional filter by agent name
            failures_only: If True, only return traces with violations

        Returns:
            List of DecisionTrace instances
        """
        stmt = select(DecisionTrace).order_by(desc(DecisionTrace.created_at))

        if agent_name:
            stmt = stmt.where(DecisionTrace.agent_name == agent_name)

        if failures_only:
            stmt = stmt.where(DecisionTrace.has_violations == "true")

        stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ID: 2b3c4d5e-6f7a-8b9c-0d1e-2f3a4b5c6d7e
    async def get_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        agent_name: str | None = None,
    ) -> list[DecisionTrace]:
        """
        Get decision traces within a date range.

        Args:
            start_date: Start of date range
            end_date: End of date range
            agent_name: Optional filter by agent name

        Returns:
            List of DecisionTrace instances
        """
        stmt = (
            select(DecisionTrace)
            .where(
                DecisionTrace.created_at >= start_date,
                DecisionTrace.created_at <= end_date,
            )
            .order_by(desc(DecisionTrace.created_at))
        )

        if agent_name:
            stmt = stmt.where(DecisionTrace.agent_name == agent_name)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ID: 3c4d5e6f-7a8b-9c0d-1e2f-3a4b5c6d7e8f
    async def get_pattern_stats(
        self,
        pattern_name: str,
        limit: int = 100,
    ) -> list[DecisionTrace]:
        """
        Get traces that used a specific pattern.

        Args:
            pattern_name: Pattern to filter by
            limit: Maximum traces to return

        Returns:
            List of DecisionTrace instances
        """
        # JSONB query: pattern_stats ? 'pattern_name'
        stmt = (
            select(DecisionTrace)
            .where(DecisionTrace.pattern_stats.has_key(pattern_name))
            .order_by(desc(DecisionTrace.created_at))
            .limit(limit)
        )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ID: 4d5e6f7a-8b9c-0d1e-2f3a-4b5c6d7e8f9a
    async def count_by_agent(self, days: int = 7) -> dict[str, int]:
        """
        Count traces by agent over the last N days.

        Args:
            days: Number of days to look back

        Returns:
            Dictionary mapping agent_name to count
        """
        from datetime import timedelta

        from sqlalchemy import func

        cutoff = datetime.now() - timedelta(days=days)

        stmt = (
            select(
                DecisionTrace.agent_name, func.count(DecisionTrace.id).label("count")
            )
            .where(DecisionTrace.created_at >= cutoff)
            .group_by(DecisionTrace.agent_name)
        )

        result = await self.session.execute(stmt)
        return {row.agent_name: row.count for row in result}

    # ID: 5e6f7a8b-9c0d-1e2f-3a4b-5c6d7e8f9a0b
    async def delete_old_traces(self, days: int = 30) -> int:
        """
        Delete traces older than N days.

        Args:
            days: Age threshold in days

        Returns:
            Number of traces deleted
        """
        from datetime import timedelta

        from sqlalchemy import delete

        cutoff = datetime.now() - timedelta(days=days)

        stmt = delete(DecisionTrace).where(DecisionTrace.created_at < cutoff)
        result = await self.session.execute(stmt)

        deleted_count = result.rowcount
        logger.info(
            "Deleted %d decision traces older than %d days", deleted_count, days
        )

        return deleted_count
