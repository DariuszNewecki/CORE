# src/will/orchestration/decision_tracer.py

"""
Records and explains autonomous decision-making chains.

ENHANCEMENT: Now persists to database for observability via `core-admin inspect decisions`.
Maintains file-based backup for reliability (safe_by_default principle).

Constitutional Compliance:
- Will layer: Makes decisions and traces them
- Mind/Body/Will separation: Uses DecisionTraceRepository (Shared) for DB persistence
- No direct database access: Receives session via dependency injection
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from shared.config import settings
from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger


if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = getLogger(__name__)


@dataclass
# ID: 1204c0b0-4a00-4dad-81d7-19b0156edcad
class Decision:
    """A single decision point in the autonomy chain."""

    timestamp: str
    agent: str
    decision_type: str
    context: dict[str, Any]
    rationale: str
    chosen_action: str
    alternatives_considered: list[str]
    confidence: float


# ID: ed96d75e-a5ea-4b93-a822-3cbbf5b889df
class DecisionTracer:
    """
    Traces and explains autonomous decision chains.

    ENHANCED: Persists traces to database for observability while maintaining
    file-based backup for reliability.

    Constitutional Note:
    This class REQUIRES AsyncSession for database persistence.
    No backward compatibility - this is the constitutional pattern.
    """

    def __init__(
        self,
        session_id: str | None = None,
        file_handler: FileHandler | None = None,
        agent_name: str | None = None,
        goal: str | None = None,
        db_session: AsyncSession | None = None,
    ):
        """
        Initialize decision tracer.

        Args:
            session_id: Unique session identifier
            file_handler: Optional FileHandler for file operations
            agent_name: Name of agent making decisions
            goal: Optional high-level goal description
            db_session: AsyncSession for database persistence.
                       If None, only file-based backup will be created.

        Constitutional Note:
        db_session is optional only because file backup is the primary safe_by_default.
        Database persistence is secondary observability feature.
        """
        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.agent_name = agent_name or "Unknown"
        self.goal = goal
        self.decisions: list[Decision] = []
        self.start_time = datetime.now()
        self._db_session = db_session

        # Keep legacy location for file-based backup
        self.trace_dir = Path("reports") / "decisions"

        # Use injected FileHandler or create a default one
        self.file_handler = file_handler or FileHandler(str(settings.REPO_PATH))

        # Ensure directory exists
        self.file_handler.ensure_dir(str(self.trace_dir))

    # ID: d259527d-5f1e-4778-8499-fa23fd49e7f5
    def record(
        self,
        agent: str,
        decision_type: str,
        rationale: str,
        chosen_action: str,
        alternatives: list[str] | None = None,
        context: dict[str, Any] | None = None,
        confidence: float = 1.0,
    ) -> None:
        """Record a decision point."""
        decision = Decision(
            timestamp=datetime.now().isoformat(),
            agent=agent,
            decision_type=decision_type,
            context=context or {},
            rationale=rationale,
            chosen_action=chosen_action,
            alternatives_considered=alternatives or [],
            confidence=confidence,
        )
        self.decisions.append(decision)
        logger.debug(
            "[%s] %s: %s (confidence: %.2f)",
            agent,
            decision_type,
            chosen_action,
            confidence,
        )

    # ID: 41368e0d-a41f-483c-9be6-14216c98a96c
    def explain_chain(self) -> str:
        """Generate human-readable explanation of the decision chain."""
        if not self.decisions:
            return "No decisions recorded yet."

        lines = [
            "=== CORE Decision Chain ===\n",
            f"Session: {self.session_id}",
            f"Agent: {self.agent_name}",
            f"Total decisions: {len(self.decisions)}\n",
        ]

        for i, d in enumerate(self.decisions, 1):
            lines.append(f"\n[{i}] {d.agent} - {d.decision_type}")
            lines.append(f"    Time: {d.timestamp}")
            lines.append(f"    Rationale: {d.rationale}")
            lines.append(f"    Chosen: {d.chosen_action}")
            if d.alternatives_considered:
                lines.append(
                    f"    Alternatives: {', '.join(d.alternatives_considered)}"
                )
            lines.append(f"    Confidence: {d.confidence:.0%}")
            if d.context:
                lines.append(f"    Context: {json.dumps(d.context, indent=8)}")

        return "\n".join(lines)

    # ID: aa09fa09-8f93-496a-bea9-62d220708268
    # ID: b7edb66b-3089-4c6a-bc65-ce9a25138df2
    async def save_trace(self) -> Path:
        """
        Save decision trace to both file (backup) and database (queryable).

        ENHANCEMENT: Now persists to DB for observability while maintaining
        file backup for reliability (safe_by_default).

        Returns:
            Path to file backup

        Constitutional Note:
        File backup always works (safe_by_default).
        Database persistence only if session was provided.
        """
        # File-based backup (safe_by_default, always works)
        trace_file = self._save_to_file()

        # Database persistence (observability, optional)
        if self._db_session is not None:
            try:
                await self._save_to_database()
            except Exception as e:
                # Never block on DB failures (safe_by_default)
                logger.warning(
                    "Failed to persist decision trace to database: %s. "
                    "File backup available at %s",
                    e,
                    trace_file,
                )
        else:
            logger.debug(
                "No database session provided, skipping DB persistence. "
                "File backup: %s",
                trace_file,
            )

        return trace_file

    def _save_to_file(self) -> Path:
        """Save to file (backup mechanism)."""
        trace_file = self.trace_dir / f"trace_{self.session_id}.json"
        rel_path = str(trace_file)

        content = json.dumps(
            {
                "session_id": self.session_id,
                "agent_name": self.agent_name,
                "goal": self.goal,
                "decisions": [asdict(d) for d in self.decisions],
            },
            indent=2,
        )

        self.file_handler.write_runtime_text(rel_path, content)
        logger.debug("Decision trace file saved: %s", rel_path)

        return trace_file

    async def _save_to_database(self) -> None:
        """
        Save to database (observability mechanism).

        Uses DecisionTraceRepository for governed DB access.

        Constitutional Note:
        This method uses the injected session (required via type system).
        Repository pattern (DecisionTraceRepository) encapsulates DB operations.
        """
        from shared.infrastructure.repositories.decision_trace_repository import (
            DecisionTraceRepository,
        )

        # Calculate statistics
        duration_ms = int((datetime.now() - self.start_time).total_seconds() * 1000)

        # Extract pattern stats
        pattern_stats = self._calculate_pattern_stats()

        # Check for violations
        has_violations, violation_count = self._check_violations()

        # Build metadata
        metadata = {
            "file_trace": str(self.trace_dir / f"trace_{self.session_id}.json"),
            "decision_types": list(set(d.decision_type for d in self.decisions)),
        }

        # Constitutional compliance: Use injected session
        repo = DecisionTraceRepository(self._db_session)

        await repo.create(
            session_id=self.session_id,
            agent_name=self.agent_name,
            decisions=[asdict(d) for d in self.decisions],
            goal=self.goal,
            pattern_stats=pattern_stats,
            has_violations=has_violations,
            violation_count=violation_count,
            duration_ms=duration_ms,
            metadata=metadata,
        )

        # Constitutional note: Caller responsible for commit/rollback
        # This follows repository pattern - repo doesn't own transaction lifecycle
        await self._db_session.commit()

        logger.info(
            "Decision trace persisted to database: session=%s decisions=%d",
            self.session_id,
            len(self.decisions),
        )

    def _calculate_pattern_stats(self) -> dict[str, int]:
        """Calculate decision pattern statistics."""
        stats: dict[str, int] = {}
        for decision in self.decisions:
            decision_type = decision.decision_type
            stats[decision_type] = stats.get(decision_type, 0) + 1
        return stats

    def _check_violations(self) -> tuple[bool, int]:
        """Check for violations in decisions."""
        violation_count = 0
        for decision in self.decisions:
            if (
                "violation" in decision.rationale.lower()
                or "error" in decision.rationale.lower()
            ):
                violation_count += 1

        has_violations = violation_count > 0
        return has_violations, violation_count


# Constitutional Note:
# This is the constitutional pattern: repository takes session via DI.
# No get_session imports anywhere - pure dependency injection.
# Caller provides session, repository uses it, caller commits.
