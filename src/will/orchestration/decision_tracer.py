# src/will/orchestration/decision_tracer.py
# ID: will.decision_tracer
"""
Records and explains autonomous decision-making chains.

ENHANCEMENT: Persists to database for observability via `core-admin inspect decisions`.
Maintains file-based backup for reliability (safe_by_default principle).

CONSTITUTIONAL FIX:
- Will does NOT import AsyncSession (or any DB primitives).
- Will does NOT import FileHandler - uses FileService from Body layer
- Callers do NOT pass sessions around.
- DB persistence is performed via a repository opened through Body session factory.
- File backup remains primary and must never fail due to DB issues.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from body.services.file_service import FileService
from shared.logger import getLogger
from shared.path_resolver import PathResolver


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

    CONSTITUTIONAL COMPLIANCE:
    - Receives FileService from Body layer (no FileHandler import)
    - No AsyncSession typing/import
    - No session injection
    - DB persistence is optional and handled via repository/session context
    """

    def __init__(
        self,
        path_resolver: PathResolver,
        session_id: str | None = None,
        file_service: FileService | None = None,
        agent_name: str | None = None,
        goal: str | None = None,
    ):
        """
        Initialize decision tracer.

        CONSTITUTIONAL FIX: Changed parameter from FileHandler to FileService

        Args:
            path_resolver: PathResolver for path resolution
            session_id: Optional session identifier
            file_service: Body layer FileService for file operations
            agent_name: Name of the agent making decisions
            goal: Goal being pursued
        """
        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self._paths = path_resolver
        self.agent_name = agent_name or "Unknown"
        self.goal = goal
        self.decisions: list[Decision] = []
        self.start_time = datetime.now()

        # Keep legacy location for file-based backup
        self.trace_dir = Path("reports") / "decisions"

        # CONSTITUTIONAL FIX: Use injected FileService or create a default one
        self.file_service = file_service or FileService(self._paths.repo_root)

        # Ensure directory exists via Body service
        self.file_service.ensure_dir(str(self.trace_dir))

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
        """Record a decision in the trace."""
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
        Save decision trace to file (always) and DB (best-effort).

        Returns:
            Path to file backup
        """
        trace_file = self._save_to_file()

        try:
            await self._save_to_database(trace_file)
        except Exception as e:
            logger.warning(
                "Failed to persist decision trace to database: %s. File backup available at %s",
                e,
                trace_file,
            )

        return trace_file

    def _save_to_file(self) -> Path:
        """
        Save trace to file system.

        CONSTITUTIONAL FIX: Uses FileService instead of FileHandler
        """
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

        # CONSTITUTIONAL FIX: Use FileService
        self.file_service.write_file(rel_path, content)
        logger.debug("Decision trace file saved: %s", rel_path)
        return trace_file

    async def _save_to_database(self, trace_file: Path) -> None:
        """
        Save to database (observability mechanism).

        Constitutional Note:
        - No session injection here.
        - Repository opens its own session context (Body-owned).
        - DB failures must never block execution (handled by caller).
        """
        from shared.infrastructure.repositories.decision_trace_repository import (
            DecisionTraceRepository,
        )

        duration_ms = int((datetime.now() - self.start_time).total_seconds() * 1000)
        pattern_stats = self._calculate_pattern_stats()
        has_violations, violation_count = self._check_violations()

        metadata = {
            "file_trace": str(trace_file),
            "decision_types": list({d.decision_type for d in self.decisions}),
        }

        async with DecisionTraceRepository.open() as repo:
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

        logger.info(
            "Decision trace persisted to database: session=%s decisions=%d",
            self.session_id,
            len(self.decisions),
        )

    def _calculate_pattern_stats(self) -> dict[str, int]:
        """Calculate statistics about decision types."""
        stats: dict[str, int] = {}
        for decision in self.decisions:
            t = decision.decision_type
            stats[t] = stats.get(t, 0) + 1
        return stats

    def _check_violations(self) -> tuple[bool, int]:
        """Check if any decisions indicate violations."""
        violation_count = 0
        for decision in self.decisions:
            r = decision.rationale.lower()
            if "violation" in r or "error" in r:
                violation_count += 1
        return violation_count > 0, violation_count
