# src/shared/infrastructure/repositories/refusal_repository.py
# ID: 4f06b9cb-148e-4da3-9dbd-4e932f47071d

"""
Refusal Repository - Governed database access for refusal records.

Constitutional Compliance:
- Repository owns DB session lifecycle via Body service_registry.session()
- Repository commits its own writes (because it owns the session)
- Never blocks operations - graceful degradation on storage failures

This repository enables constitutional refusal tracking and the
`core-admin inspect refusals` command.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from sqlalchemy import desc, select

from body.services.service_registry import service_registry
from shared.infrastructure.database.models.refusals import RefusalRecord
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 1930d0d3-30a5-4902-b6c2-a5125c287ea5
class RefusalRepository:
    """
    Repository for refusal record database operations.

    Constitutional Pattern:
    - Owns session lifecycle (via service_registry)
    - Commits its own writes
    - Gracefully degrades on failures (logs but doesn't raise)
    """

    @asynccontextmanager
    async def _session(self):
        """Get async DB session from service registry."""
        async with service_registry.session() as session:
            yield session

    # ID: 1f9de411-5616-4f18-84be-1c6bd99fd632
    async def record_refusal(
        self,
        component_id: str,
        phase: str,
        refusal_type: str,
        reason: str,
        suggested_action: str,
        original_request: str = "",
        confidence: float = 0.0,
        context_data: dict[str, Any] | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> RefusalRecord | None:
        """
        Record a constitutional refusal.

        CONSTITUTIONAL: Never raises - gracefully degrades on storage failure.

        Args:
            component_id: Component that refused
            phase: Component phase (EXECUTION, PARSE, etc.)
            refusal_type: Category (boundary, confidence, extraction, etc.)
            reason: Constitutional reason with policy citation
            suggested_action: What user should do
            original_request: The refused request (for audit)
            confidence: Confidence score at refusal time
            context_data: Additional context
            session_id: Decision trace session ID (optional)
            user_id: User who received refusal (optional)

        Returns:
            RefusalRecord if stored successfully, None on failure
        """
        try:
            async with self._session() as session:
                record = RefusalRecord(
                    component_id=component_id,
                    phase=phase,
                    refusal_type=refusal_type,
                    reason=reason,
                    suggested_action=suggested_action,
                    original_request=original_request,
                    confidence=confidence,
                    context_data=context_data or {},
                    session_id=session_id,
                    user_id=user_id,
                )

                session.add(record)
                await session.commit()
                await session.refresh(record)

                logger.debug(
                    "Refusal recorded: %s by %s (type: %s)",
                    record.id,
                    component_id,
                    refusal_type,
                )
                return record

        except Exception as e:
            logger.warning(
                "Failed to record refusal (non-blocking): %s",
                e,
                exc_info=True,
            )
            return None

    # ID: 22c5bf48-3b45-4817-9dbb-96bcdb3f345d
    async def get_recent(
        self,
        limit: int = 20,
        refusal_type: str | None = None,
        component_id: str | None = None,
    ) -> list[RefusalRecord]:
        """
        Get recent refusals with optional filtering.

        Args:
            limit: Maximum number of records (1-100)
            refusal_type: Filter by type (boundary, confidence, etc.)
            component_id: Filter by component

        Returns:
            List of RefusalRecord objects, newest first
        """
        limit = max(1, min(limit, 100))  # Clamp to 1-100

        try:
            async with self._session() as session:
                query = select(RefusalRecord).order_by(desc(RefusalRecord.created_at))

                if refusal_type:
                    query = query.where(RefusalRecord.refusal_type == refusal_type)

                if component_id:
                    query = query.where(RefusalRecord.component_id == component_id)

                query = query.limit(limit)

                result = await session.execute(query)
                return list(result.scalars().all())

        except Exception as e:
            logger.error("Failed to query refusals: %s", e, exc_info=True)
            return []

    # ID: 8a1044fd-1f8a-4a1b-8e04-7aabc959cffb
    async def get_by_session(self, session_id: str) -> list[RefusalRecord]:
        """
        Get all refusals for a specific decision trace session.

        Args:
            session_id: Decision trace session ID

        Returns:
            List of RefusalRecord objects for this session
        """
        try:
            async with self._session() as session:
                query = (
                    select(RefusalRecord)
                    .where(RefusalRecord.session_id == session_id)
                    .order_by(RefusalRecord.created_at)
                )

                result = await session.execute(query)
                return list(result.scalars().all())

        except Exception as e:
            logger.error(
                "Failed to query refusals for session %s: %s",
                session_id,
                e,
                exc_info=True,
            )
            return []

    # ID: ae6795f1-32b2-4128-9770-bb71881984d2
    async def get_by_type(
        self, refusal_type: str, limit: int = 50
    ) -> list[RefusalRecord]:
        """
        Get refusals by type for analysis.

        Args:
            refusal_type: Refusal category
            limit: Maximum records (1-100)

        Returns:
            List of RefusalRecord objects of this type
        """
        return await self.get_recent(
            limit=limit, refusal_type=refusal_type, component_id=None
        )

    # ID: d21057f9-7f64-4783-8bf7-dd1ec8d0ddca
    async def get_statistics(self, days: int = 7) -> dict[str, Any]:
        """
        Get refusal statistics for analysis.

        Args:
            days: Number of days to analyze

        Returns:
            Dictionary with refusal statistics
        """
        try:
            async with self._session() as session:
                # Get refusals from last N days
                cutoff = datetime.now().replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                from datetime import timedelta

                cutoff = cutoff - timedelta(days=days - 1)

                query = select(RefusalRecord).where(RefusalRecord.created_at >= cutoff)

                result = await session.execute(query)
                refusals = list(result.scalars().all())

                # Calculate statistics
                stats = {
                    "total_refusals": len(refusals),
                    "days_analyzed": days,
                    "by_type": {},
                    "by_component": {},
                    "by_phase": {},
                    "avg_confidence": 0.0,
                }

                if not refusals:
                    return stats

                # Count by type
                for refusal in refusals:
                    # By type
                    type_key = refusal.refusal_type
                    stats["by_type"][type_key] = stats["by_type"].get(type_key, 0) + 1

                    # By component
                    comp_key = refusal.component_id
                    stats["by_component"][comp_key] = (
                        stats["by_component"].get(comp_key, 0) + 1
                    )

                    # By phase
                    phase_key = refusal.phase
                    stats["by_phase"][phase_key] = (
                        stats["by_phase"].get(phase_key, 0) + 1
                    )

                # Average confidence
                confidences = [r.confidence for r in refusals]
                stats["avg_confidence"] = sum(confidences) / len(confidences)

                return stats

        except Exception as e:
            logger.error("Failed to calculate refusal statistics: %s", e, exc_info=True)
            return {
                "total_refusals": 0,
                "days_analyzed": days,
                "by_type": {},
                "by_component": {},
                "by_phase": {},
                "avg_confidence": 0.0,
            }

    # ID: e7c9af63-f216-414d-8a3f-9c0edf070842
    async def count_by_type(self, days: int = 7) -> dict[str, int]:
        """
        Count refusals by type for the last N days.

        Args:
            days: Number of days to analyze

        Returns:
            Dictionary mapping refusal_type -> count
        """
        stats = await self.get_statistics(days)
        return stats.get("by_type", {})
