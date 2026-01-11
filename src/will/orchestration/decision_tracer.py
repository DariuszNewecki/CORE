# src/will/orchestration/decision_tracer.py

"""
Records and explains autonomous decision-making chains.

ENHANCEMENT: Now persists to database for observability via `core-admin inspect decisions`.
Maintains file-based backup for reliability (safe_by_default principle).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from shared.config import settings
from shared.infrastructure.database.session_manager import get_session
from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger


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
    """

    def __init__(
        self,
        session_id: str | None = None,
        file_handler: FileHandler | None = None,
        agent_name: str | None = None,
        goal: str | None = None,
    ):
        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.agent_name = agent_name or "Unknown"
        self.goal = goal
        self.decisions: list[Decision] = []
        self.start_time = datetime.now()

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
    # CONSTITUTIONAL FIX: Promoted to async to handle DB persistence
    # ID: b7edb66b-3089-4c6a-bc65-ce9a25138df2
    async def save_trace(self) -> Path:
        """
        Save decision trace to both file (backup) and database (queryable).

        ENHANCEMENT: Now persists to DB for observability while maintaining
        file backup for reliability (safe_by_default).

        Returns:
            Path to file backup
        """
        # File-based backup (legacy, always works)
        trace_file = self._save_to_file()

        # Database persistence (new, for observability)
        try:
            # CONSTITUTIONAL FIX: Added await
            await self._save_to_database()
        except Exception as e:
            # Never block on DB failures (safe_by_default)
            logger.warning(
                "Failed to persist decision trace to database: %s. "
                "File backup available at %s",
                e,
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

        # Persist to database
        async with get_session() as session:
            repo = DecisionTraceRepository(session)

            await repo.create(
                session_id=self.session_id,
                agent_name=self.agent_name,
                decisions=[asdict(d) for d in self.decisions],
                goal=self.goal,
                pattern_stats=pattern_stats,
                has_violations=has_violations,
                violation_count=violation_count,
                duration_ms=duration_ms,
                metadata=metadata,  # Note: Repo maps this to extra_metadata column
            )

            await session.commit()

        logger.info(
            "Decision trace persisted to database: session=%s decisions=%d",
            self.session_id,
            len(self.decisions),
        )

    def _calculate_pattern_stats(self) -> dict[str, int] | None:
        """Calculate pattern usage frequency."""
        patterns = {}

        for decision in self.decisions:
            # Extract pattern from context if available
            pattern_id = decision.context.get("pattern_id")
            if pattern_id:
                patterns[pattern_id] = patterns.get(pattern_id, 0) + 1

        return patterns if patterns else None

    def _check_violations(self) -> tuple[bool | None, int | None]:
        """Check if trace contains any violations."""
        violation_count = 0

        for decision in self.decisions:
            # Check for correction/violation-related decision types
            if "correction" in decision.decision_type.lower():
                violation_count += 1
            elif "violation" in decision.decision_type.lower():
                violation_count += 1

            # Check context for violation indicators
            if decision.context.get("violations"):
                # Handle both int and list-length cases
                v = decision.context.get("violations")
                violation_count += v if isinstance(v, int) else len(v)

        has_violations = violation_count > 0 if violation_count else None

        return has_violations, violation_count if violation_count else None

    # ID: format_trace (for compatibility)
    # ID: 5fe65876-5a73-47be-b58b-a4ad47613346
    def format_trace(self) -> str:
        """Alias for explain_chain() for backward compatibility."""
        return self.explain_chain()
