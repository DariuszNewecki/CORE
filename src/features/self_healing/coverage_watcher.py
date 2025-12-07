# src/features/self_healing/coverage_watcher.py

"""
Constitutional coverage watcher that monitors for violations and triggers
autonomous remediation when coverage falls below the minimum threshold.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta

from mind.governance.checks.coverage_check import CoverageGovernanceCheck
from shared.config import settings
from shared.context import CoreContext
from shared.logger import getLogger

from features.self_healing.coverage_remediation_service import remediate_coverage

logger = getLogger(__name__)


@dataclass
# ID: 40e7eabc-d098-45c9-bfce-ab5f1a252d4d
class CoverageViolation:
    """Represents a coverage violation that needs remediation."""

    timestamp: datetime
    current_coverage: float
    required_coverage: float
    delta: float
    critical_paths_violated: list[str]
    auto_remediate: bool = True


# ID: 586c3b59-fe2d-4cfb-ba25-c13fd74b8336
class CoverageWatcher:
    """
    Monitors test coverage and triggers autonomous remediation when violations occur.
    """

    def __init__(self):
        self.policy = settings.load(
            "charter.policies.governance.quality_assurance_policy"
        )
        self.checker = CoverageGovernanceCheck()
        self.state_file = settings.REPO_PATH / "work" / "testing" / "watcher_state.json"
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

    # ID: 1379872b-e1b3-4446-b298-a652a811a8df
    async def check_and_remediate(
        self, context: CoreContext, auto_remediate: bool = True
    ) -> dict:
        """
        Checks coverage and triggers remediation if needed.
        """
        logger.info("Constitutional Coverage Watch")
        findings = await self.checker.execute()
        if not findings:
            logger.info("Coverage compliant - no action needed")
            self._record_compliant_state()
            return {"status": "compliant", "action": "none", "findings": []}
        violation = self._analyze_findings(findings)
        logger.warning("Constitutional Violation Detected")
        logger.info(f"   Current: {violation.current_coverage}%")
        logger.info(f"   Required: {violation.required_coverage}%")
        logger.info(f"   Gap: {abs(violation.delta):.1f}%")
        if not auto_remediate:
            logger.warning("Auto-remediation disabled - manual intervention required")
            return {
                "status": "violation",
                "action": "manual_required",
                "violation": violation,
                "findings": findings,
            }
        if self._in_cooldown():
            logger.warning("Remediation in cooldown period - skipping")
            return {
                "status": "violation",
                "action": "cooldown",
                "violation": violation,
                "findings": findings,
            }
        logger.info("Triggering Autonomous Remediation")
        try:
            remediation_result = await remediate_coverage(
                context.cognitive_service, context.auditor_context
            )
            self._record_remediation(violation, remediation_result)
            post_findings = await self.checker.execute()
            if not post_findings:
                logger.info("Remediation successful - coverage restored!")
                return {"status": "remediated", "compliant": True}
            else:
                logger.warning("Partial remediation - some violations remain")
                return {"status": "partial_remediation", "compliant": False}
        except Exception as e:
            logger.error(f"Remediation failed: {e}", exc_info=True)
            return {"status": "remediation_failed", "error": str(e)}

    def _analyze_findings(self, findings: list) -> CoverageViolation:
        main_finding = next(
            (f for f in findings if f.check_id == "coverage.minimum_threshold"),
            findings[0] if findings else None,
        )
        if not main_finding:
            return CoverageViolation(
                timestamp=datetime.now(),
                current_coverage=0,
                required_coverage=75,
                delta=-75,
                critical_paths_violated=[],
            )
        context = main_finding.context or {}
        critical_paths = [
            f.file_path for f in findings if f.check_id == "coverage.critical_path"
        ]
        return CoverageViolation(
            timestamp=datetime.now(),
            current_coverage=context.get("current", 0),
            required_coverage=context.get("required", 75),
            delta=context.get("delta", 0),
            critical_paths_violated=critical_paths,
        )

    def _in_cooldown(self) -> bool:
        if not self.state_file.exists():
            return False
        try:
            state = json.loads(self.state_file.read_text())
            last_remediation = state.get("last_remediation")
            if not last_remediation:
                return False
            last_time = datetime.fromisoformat(last_remediation)
            cooldown_hours = self.policy.get("coverage_config", {}).get(
                "remediation_cooldown_hours", 24
            )
            return datetime.now() - last_time < timedelta(hours=cooldown_hours)
        except Exception as e:
            logger.debug("Could not check cooldown: %s", e)
        return False

    def _record_compliant_state(self) -> None:
        try:
            state = {"last_check": datetime.now().isoformat(), "status": "compliant"}
            if self.state_file.exists():
                existing = json.loads(self.state_file.read_text())
                state.update(existing)
            self.state_file.write_text(json.dumps(state, indent=2))
        except Exception as e:
            logger.debug("Could not record state: %s", e)

    def _record_remediation(self, violation: CoverageViolation, result: dict) -> None:
        try:
            state = {}
            if self.state_file.exists():
                state = json.loads(self.state_file.read_text())
            state.update(
                {
                    "last_check": datetime.now().isoformat(),
                    "last_remediation": datetime.now().isoformat(),
                    "status": "remediated",
                    "last_violation": {
                        "timestamp": violation.timestamp.isoformat(),
                        "current_coverage": violation.current_coverage,
                        "required_coverage": violation.required_coverage,
                        "delta": violation.delta,
                    },
                    "last_result": {
                        "status": result.get("status"),
                        "succeeded": result.get("succeeded", 0),
                        "failed": result.get("failed", 0),
                        "final_coverage": result.get("final_coverage", 0),
                    },
                }
            )
            state.setdefault("remediation_history", []).append(
                {
                    "timestamp": violation.timestamp.isoformat(),
                    "coverage_before": violation.current_coverage,
                    "coverage_after": result.get("final_coverage", 0),
                    "tests_generated": result.get("succeeded", 0),
                }
            )
            state["remediation_history"] = state["remediation_history"][-10:]
            self.state_file.write_text(json.dumps(state, indent=2))
        except Exception as e:
            logger.debug("Could not record remediation: %s", e)


# ID: 547d5f4c-c028-4386-975a-02cf7792ee85
async def watch_and_remediate(
    context: CoreContext, auto_remediate: bool = True
) -> dict:
    """
    Public interface for coverage watching.
    Now requires the CoreContext to be passed in.
    """
    watcher = CoverageWatcher()
    return await watcher.check_and_remediate(context, auto_remediate=auto_remediate)
