# src/features/self_healing/coverage_watcher.py
"""
Constitutional coverage watcher that monitors for violations and triggers
autonomous remediation when coverage falls below the minimum threshold.

This service can run as:
1. A post-integration check (triggered by CI/workflow)
2. A scheduled background service
3. An on-demand check
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from core.cognitive_service import CognitiveService
from rich.console import Console
from shared.config import settings
from shared.logger import getLogger

from features.governance.audit_context import AuditorContext
from features.governance.checks.coverage_check import CoverageGovernanceCheck
from features.self_healing.coverage_remediation_service import remediate_coverage

log = getLogger(__name__)
console = Console()


@dataclass
# ID: TBD
# ID: 695cf5aa-2546-4992-92f3-84e96ae2b557
class CoverageViolation:
    """Represents a coverage violation that needs remediation."""

    timestamp: datetime
    current_coverage: float
    required_coverage: float
    delta: float
    critical_paths_violated: list[str]
    auto_remediate: bool = True


# ID: TBD
# ID: df922362-15e3-4f89-8c9c-7c4d0ea47612
class CoverageWatcher:
    """
    Monitors test coverage and triggers autonomous remediation when violations occur.

    This implements the constitutional requirement that CORE maintains
    minimum coverage and automatically heals when it drops below threshold.
    """

    def __init__(self):
        self.policy = settings.load(
            "charter.policies.governance.quality_assurance_policy"
        )
        self.checker = CoverageGovernanceCheck()
        self.state_file = settings.REPO_PATH / "work" / "testing" / "watcher_state.json"
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

    # ID: efe54478-0d5d-49f0-84bb-8ee5f7a309d9
    async def check_and_remediate(self, auto_remediate: bool = True) -> dict:
        """
        Checks coverage and triggers remediation if needed.

        Args:
            auto_remediate: If True, automatically trigger remediation on violations

        Returns:
            Dict with check results and any remediation actions taken
        """
        console.print("\n[bold cyan]🔍 Constitutional Coverage Watch[/bold cyan]")

        # Run coverage check
        findings = await self.checker.execute()

        if not findings:
            console.print("[green]✅ Coverage compliant - no action needed[/green]")
            self._record_compliant_state()
            return {
                "status": "compliant",
                "action": "none",
                "findings": [],
            }

        # Analyze violations
        violation = self._analyze_findings(findings)

        console.print("\n[bold red]⚠️  Constitutional Violation Detected[/bold red]")
        console.print(f"   Current: {violation.current_coverage}%")
        console.print(f"   Required: {violation.required_coverage}%")
        console.print(f"   Gap: {abs(violation.delta):.1f}%")

        # Check if we should remediate
        if not auto_remediate:
            console.print(
                "\n[yellow]Auto-remediation disabled - manual intervention required[/yellow]"
            )
            return {
                "status": "violation",
                "action": "manual_required",
                "violation": violation,
                "findings": findings,
            }

        # Check remediation cooldown
        if self._in_cooldown():
            console.print(
                "\n[yellow]Remediation in cooldown period - skipping[/yellow]"
            )
            return {
                "status": "violation",
                "action": "cooldown",
                "violation": violation,
                "findings": findings,
            }

        # Trigger autonomous remediation
        console.print("\n[bold cyan]🤖 Triggering Autonomous Remediation[/bold cyan]")

        try:
            cognitive = CognitiveService()
            auditor = AuditorContext()

            remediation_result = await remediate_coverage(cognitive, auditor)

            # Record remediation attempt
            self._record_remediation(violation, remediation_result)

            # Re-check coverage
            post_findings = await self.checker.execute()

            if not post_findings:
                console.print(
                    "\n[bold green]✅ Remediation successful - coverage restored![/bold green]"
                )
                return {
                    "status": "remediated",
                    "action": "auto_remediation",
                    "violation": violation,
                    "remediation": remediation_result,
                    "compliant": True,
                }
            else:
                console.print(
                    "\n[yellow]⚠️  Partial remediation - some violations remain[/yellow]"
                )
                return {
                    "status": "partial_remediation",
                    "action": "auto_remediation",
                    "violation": violation,
                    "remediation": remediation_result,
                    "remaining_findings": post_findings,
                    "compliant": False,
                }

        except Exception as e:
            log.error(f"Remediation failed: {e}", exc_info=True)
            console.print(f"\n[red]❌ Remediation failed: {e}[/red]")
            return {
                "status": "remediation_failed",
                "action": "auto_remediation",
                "violation": violation,
                "error": str(e),
            }

    def _analyze_findings(self, findings: list) -> CoverageViolation:
        """
        Analyzes audit findings to extract violation details.

        Args:
            findings: List of AuditFinding objects

        Returns:
            CoverageViolation with aggregated details
        """
        # Find the main coverage finding
        main_finding = next(
            (f for f in findings if f.rule_id == "coverage.minimum_threshold"),
            findings[0] if findings else None,
        )

        if not main_finding:
            # Shouldn't happen, but handle gracefully
            return CoverageViolation(
                timestamp=datetime.now(),
                current_coverage=0,
                required_coverage=75,
                delta=-75,
                critical_paths_violated=[],
            )

        context = main_finding.context or {}

        # Extract critical path violations
        critical_paths = [
            f.file_path for f in findings if f.rule_id == "coverage.critical_path"
        ]

        return CoverageViolation(
            timestamp=datetime.now(),
            current_coverage=context.get("current", 0),
            required_coverage=context.get("required", 75),
            delta=context.get("delta", 0),
            critical_paths_violated=critical_paths,
        )

    def _in_cooldown(self) -> bool:
        """
        Checks if we're in cooldown period after recent remediation.

        Prevents excessive remediation attempts in short succession.

        Returns:
            True if in cooldown, False otherwise
        """
        import json

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

            if datetime.now() - last_time < timedelta(hours=cooldown_hours):
                return True

        except Exception as e:
            log.debug(f"Could not check cooldown: {e}")

        return False

    def _record_compliant_state(self) -> None:
        """Records that coverage is currently compliant."""
        import json

        try:
            state = {
                "last_check": datetime.now().isoformat(),
                "status": "compliant",
            }

            if self.state_file.exists():
                existing = json.loads(self.state_file.read_text())
                state.update(existing)

            self.state_file.write_text(json.dumps(state, indent=2))
        except Exception as e:
            log.debug(f"Could not record state: {e}")

    def _record_remediation(self, violation: CoverageViolation, result: dict) -> None:
        """Records a remediation attempt for audit trail and cooldown."""
        import json

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

            # Keep history
            if "remediation_history" not in state:
                state["remediation_history"] = []

            state["remediation_history"].append(
                {
                    "timestamp": violation.timestamp.isoformat(),
                    "coverage_before": violation.current_coverage,
                    "coverage_after": result.get("final_coverage", 0),
                    "tests_generated": result.get("succeeded", 0),
                }
            )

            # Keep only last 10 entries
            state["remediation_history"] = state["remediation_history"][-10:]

            self.state_file.write_text(json.dumps(state, indent=2))

        except Exception as e:
            log.debug(f"Could not record remediation: {e}")


# ID: TBD
# ID: a57f7022-573f-4b13-bf14-8919d47f72bb
async def watch_and_remediate(auto_remediate: bool = True) -> dict:
    """
    Public interface for coverage watching.

    This can be called from:
    - Integration workflow (post-commit check)
    - CI pipeline (PR checks)
    - Scheduled cron job
    - Manual CLI command

    Args:
        auto_remediate: If True, automatically trigger remediation

    Returns:
        Dict with watch results and actions taken
    """
    watcher = CoverageWatcher()
    return await watcher.check_and_remediate(auto_remediate=auto_remediate)
