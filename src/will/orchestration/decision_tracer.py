# src/will/orchestration/decision_tracer.py

"""Records and explains autonomous decision-making chains."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from shared.infrastructure.storage.file_handler import FileHandler  # <--- NEW IMPORT
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
    """Traces and explains autonomous decision chains."""

    def __init__(
        self, session_id: str | None = None, file_handler: FileHandler | None = None
    ):
        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.decisions: list[Decision] = []
        self.trace_dir = Path("reports/decisions")

        # Use injected FileHandler or create a default one (safe default for Body)
        self.file_handler = file_handler or FileHandler(Path("."))

        # Delegate mkdir to Body layer
        self.file_handler.ensure_directory(self.trace_dir)

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
    ):
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
        logger.info(
            "[%s] %s: %s (confidence: %s)",
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
    def save_trace(self):
        """Save decision trace to file."""
        trace_file = self.trace_dir / f"trace_{self.session_id}.json"

        content = json.dumps(
            {
                "session_id": self.session_id,
                "decisions": [asdict(d) for d in self.decisions],
            },
            indent=2,
        )

        # Delegate write to Body layer
        self.file_handler.write_file(trace_file, content)

        logger.info("Decision trace saved: %s", trace_file)
        return trace_file
