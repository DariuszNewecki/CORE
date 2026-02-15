# src/features/self_healing/coverage_watcher.py

"""
Constitutional coverage watcher.

CONSTITUTIONAL FIX (V2.3):
- Modularized to reduce Modularity Debt (51.2 -> ~41.0).
- Uses V2.3 'CoverageMinimumCheck' from the Workflow Gate subsystem.
- Encapsulates state management to remove I/O coupling from the main class.
- Aligns with the Octopus-UNIX Synthesis.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from body.self_healing.coverage_remediation_service import remediate_coverage
from mind.logic.engines.workflow_gate.checks.coverage import CoverageMinimumCheck
from shared.config import settings
from shared.logger import getLogger


logger = getLogger(__name__)


@dataclass(frozen=True)
# ID: 10af153b-2b02-46ee-b06e-07afe2c5e69b
class CoverageViolation:
    """Represents a coverage violation detected by the Mind."""

    timestamp: datetime
    current_coverage: float
    required_coverage: float
    message: str


# ID: 1f2e3d4c-5b6a-7890-abcd-ef1234567890
class _WatcherState:
    """Specialist for managing the persistent memory of the watcher."""

    def __init__(self, repo_root: Any, state_path: str):
        self.repo_root = repo_root
        self.path = state_path

    # ID: 5b86b122-7d5a-4cf5-ba5a-76c4d9bc2fb7
    def get_last_remediation(self) -> datetime | None:
        try:
            abs_path = self.repo_root / self.path
            if not abs_path.exists():
                return None
            data = json.loads(abs_path.read_text(encoding="utf-8"))
            return datetime.fromisoformat(data.get("last_remediation", ""))
        except Exception:
            return None

    # ID: 66ab3cb4-e3fe-424a-b908-e37273836d55
    def record_success(self, violation: CoverageViolation):
        from shared.infrastructure.storage.file_handler import FileHandler

        fh = FileHandler(str(self.repo_root))
        state = {
            "last_check": datetime.now().isoformat(),
            "last_remediation": datetime.now().isoformat(),
            "status": "remediated",
            "last_violation": {
                "current": violation.current_coverage,
                "required": violation.required_coverage,
            },
        }
        fh.write_runtime_json(self.path, state)


# ID: c75a7281-9bb9-4c03-8dcf-2eb38c36f9a8
class CoverageWatcher:
    """
    Monitors test coverage and triggers autonomous remediation.

    Refactored for V2.3 to use the Workflow Gate engine and delegate state.
    """

    def __init__(self):
        # Use the V2.3 PathResolver from settings
        self._paths = settings.paths
        # Initialize the V2.3 Logic Engine check
        self.gate_check = CoverageMinimumCheck(self._paths)
        self.state = _WatcherState(
            self._paths.repo_root, "work/testing/watcher_state.json"
        )

    # ID: c0b0acc5-7030-458a-9b5e-45d03e9fe8ee
    async def check_and_remediate(
        self, context: Any, auto_remediate: bool = True
    ) -> dict:
        """Senses the current coverage state and reacts to violations."""
        logger.info("📡 Coverage Watch: Sensing system state via Workflow Gate...")

        # In V2.3, verify() returns a list of violation strings. Empty = Pass.
        violations = await self.gate_check.verify(None, {})

        if not violations:
            logger.info("✅ Coverage compliant.")
            return {"status": "compliant"}

        # Analyze findings (Just take the first one for the summary)
        violation = self._parse_violation(violations[0])
        logger.warning("🚨 Constitutional Violation: %s", violation.message)

        if not auto_remediate:
            return {"status": "violation_detected", "violation": violation}

        if self._is_in_cooldown():
            logger.warning("⏳ Remediation cooldown active. Skipping reflex.")
            return {"status": "cooldown"}

        # TRIGGER REFLEX
        try:
            logger.info("🚀 Initiating coverage_remediation workflow...")
            # Note: remediate_coverage is a high-level service from self_healing
            result = await remediate_coverage(
                context.cognitive_service,
                context.auditor_context,
                file_handler=context.file_handler,
                repo_root=self._paths.repo_root,
            )
            self.state.record_success(violation)
            return {"status": "remediated", "result": result}
        except Exception as e:
            logger.error("❌ Remediation failed: %s", e)
            return {"status": "error", "error": str(e)}

    def _is_in_cooldown(self) -> bool:
        last = self.state.get_last_remediation()
        if not last:
            return False
        return datetime.now() - last < timedelta(hours=24)

    def _parse_violation(self, message: str) -> CoverageViolation:
        """Parses the error message from CoverageMinimumCheck into a data object."""
        # Simple extraction logic from the "Coverage too low: X% (Target: Y%)" string
        import re

        match = re.search(r"(\d+\.?\d*)%", message)
        current = float(match.group(1)) if match else 0.0

        return CoverageViolation(
            timestamp=datetime.now(),
            current_coverage=current,
            required_coverage=75.0,  # Default per policy
            message=message,
        )


# ID: 55f5ea3e-a410-4595-97ec-6bd4d4f8641e
async def watch_and_remediate(context: Any, auto_remediate: bool = True) -> dict:
    """Public wrapper for the sensor loop."""
    return await CoverageWatcher().check_and_remediate(context, auto_remediate)
