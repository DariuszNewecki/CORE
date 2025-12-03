# src/will/orchestration/decision_tracer.py
"""Records and explains autonomous decision-making chains."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from shared.logger import getLogger

logger = getLogger(__name__)


@dataclass
# ID: c5518b4f-a138-407b-87b3-f036880b765b
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


# ID: 8d1ec1ce-07be-47e2-b2c2-c806a7e8d179
class DecisionTracer:
    """Traces and explains autonomous decision chains."""

    def __init__(self, session_id: str | None = None):
        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.decisions: list[Decision] = []
        self.trace_dir = Path("reports/decisions")
        self.trace_dir.mkdir(parents=True, exist_ok=True)

    # ID: 26d6bd8f-fa12-4d32-b9de-26dbf3f2f940
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
            f"[{agent}] {decision_type}: {chosen_action} (confidence: {confidence:.2f})"
        )

    # ID: 902aaaba-e3d9-4b8d-9f23-5291869bcee0
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

    # ID: dbf6f1e6-cf88-42a8-9841-63da6e053269
    def save_trace(self):
        """Save decision trace to file."""
        trace_file = self.trace_dir / f"trace_{self.session_id}.json"
        with open(trace_file, "w") as f:
            json.dump(
                {
                    "session_id": self.session_id,
                    "decisions": [asdict(d) for d in self.decisions],
                },
                f,
                indent=2,
            )
        logger.info(f"Decision trace saved: {trace_file}")
        return trace_file
