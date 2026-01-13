# src/features/self_healing/coverage_watcher.py
# ID: c75a7281-9bb9-4c03-8dcf-2eb38c36f9a8

"""
Constitutional coverage watcher that monitors for violations and triggers
autonomous remediation when coverage falls below the minimum threshold.

MODERNIZATION: Updated to use the settings.paths (PathResolver) standard
instead of the deprecated settings.load() shim.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta

import yaml

from features.self_healing.coverage_remediation_service import remediate_coverage
from mind.governance.checks.coverage_check import CoverageGovernanceCheck
from shared.config import settings
from shared.context import CoreContext
from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger


logger = getLogger(__name__)


@dataclass
# ID: 10af153b-2b02-46ee-b06e-07afe2c5e69b
class CoverageViolation:
    """Represents a coverage violation that needs remediation."""

    timestamp: datetime
    current_coverage: float
    required_coverage: float
    delta: float
    critical_paths_violated: list[str]
    auto_remediate: bool = True


# ID: c75a7281-9bb9-4c03-8dcf-2eb38c36f9a8
class CoverageWatcher:
    """
    Monitors test coverage and triggers autonomous remediation when violations occur.
    """

    def __init__(self):
        # MODERNIZATION: Resolve policy path via PathResolver (SSOT)
        try:
            policy_path = settings.paths.policy("quality_assurance")
            self.policy = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(
                "Could not load quality_assurance policy via resolver: %s. Using safe defaults.",
                e,
            )
            self.policy = {}

        self.checker = CoverageGovernanceCheck()
        self.fh = FileHandler(str(settings.REPO_PATH))

        # Relative path for the governed FileHandler API
        self.state_rel_path = "work/testing/watcher_state.json"
        self.state_file_abs = settings.REPO_PATH / self.state_rel_path

    # ID: c0b0acc5-7030-458a-9b5e-45d03e9fe8ee
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
        logger.warning(
            "Constitutional Violation Detected: Current %s%% vs Required %s%%",
            violation.current_coverage,
            violation.required_coverage,
        )

        if not auto_remediate:
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

        logger.info("Triggering Autonomous Remediation...")
        try:
            # Calls the V2-aligned service (updated in Step 2.4)
            remediation_result = await remediate_coverage(
                context.cognitive_service, context.auditor_context
            )
            self._record_remediation(violation, remediation_result)

            # Post-remediation verification
            post_findings = await self.checker.execute()
            if not post_findings:
                logger.info("✅ Remediation successful - coverage restored!")
                return {"status": "remediated", "compliant": True}
            else:
                logger.warning("⚠️ Partial remediation - some violations remain")
                return {"status": "partial_remediation", "compliant": False}

        except Exception as e:
            logger.error("Remediation failed: %s", e, exc_info=True)
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

        finding_context = main_finding.context or {}
        critical_paths = [
            f.file_path for f in findings if f.check_id == "coverage.critical_path"
        ]
        return CoverageViolation(
            timestamp=datetime.now(),
            current_coverage=finding_context.get("current", 0),
            required_coverage=finding_context.get("required", 75),
            delta=finding_context.get("delta", 0),
            critical_paths_violated=critical_paths,
        )

    def _in_cooldown(self) -> bool:
        if not self.state_file_abs.exists():
            return False
        try:
            state = json.loads(self.state_file_abs.read_text(encoding="utf-8"))
            last_remediation = state.get("last_remediation")
            if not last_remediation:
                return False
            last_time = datetime.fromisoformat(last_remediation)

            # Use settings for cooldown or default to 24h
            cooldown_hours = self.policy.get("coverage_config", {}).get(
                "remediation_cooldown_hours", 24
            )
            return datetime.now() - last_time < timedelta(hours=cooldown_hours)
        except Exception:
            return False

    def _record_compliant_state(self) -> None:
        try:
            state = {"last_check": datetime.now().isoformat(), "status": "compliant"}
            if self.state_file_abs.exists():
                existing = json.loads(self.state_file_abs.read_text(encoding="utf-8"))
                state.update(existing)

            self.fh.write_runtime_json(self.state_rel_path, state)
        except Exception as e:
            logger.debug("Could not record state: %s", e)

    def _record_remediation(self, violation: CoverageViolation, result: dict) -> None:
        try:
            state = {}
            if self.state_file_abs.exists():
                state = json.loads(self.state_file_abs.read_text(encoding="utf-8"))
            state.update(
                {
                    "last_check": datetime.now().isoformat(),
                    "last_remediation": datetime.now().isoformat(),
                    "status": "remediated",
                    "last_violation": {
                        "timestamp": violation.timestamp.isoformat(),
                        "current_coverage": violation.current_coverage,
                        "required_coverage": violation.required_coverage,
                    },
                    "last_result": {
                        "status": result.get("status"),
                        "succeeded": result.get("succeeded", 0),
                    },
                }
            )
            self.fh.write_runtime_json(self.state_rel_path, state)
        except Exception as e:
            logger.debug("Could not record remediation: %s", e)


# ID: 1aa4e4ef-2362-44b7-8aae-7d6af69cb799
async def watch_and_remediate(
    context: CoreContext, auto_remediate: bool = True
) -> dict:
    """Public interface for coverage watching."""
    watcher = CoverageWatcher()
    return await watcher.check_and_remediate(context, auto_remediate=auto_remediate)
