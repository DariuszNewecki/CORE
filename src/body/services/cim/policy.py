# src/body/services/cim/policy.py
# ID: body.services.cim.policy

"""
CIM Policy Evaluator - Turn diffs into actionable findings.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from shared.logger import getLogger

from .models import CensusDiff, Finding, PolicyEvaluation


logger = getLogger(__name__)


# ID: 59e702a3-067e-4aaf-948b-32d99c5111d4
class PolicyEvaluator:
    """Evaluate census diffs against policy thresholds."""

    def __init__(self, thresholds_path: Path):
        """Load policy thresholds from YAML."""
        self.thresholds_path = thresholds_path

        if thresholds_path.exists():
            with thresholds_path.open() as f:
                self.thresholds = yaml.safe_load(f) or {}
        else:
            logger.warning("No thresholds file found: %s", thresholds_path)
            self.thresholds = {}

    # ID: 5650882c-06bb-429d-999c-c0d7845d0b08
    def evaluate(self, diff: CensusDiff) -> PolicyEvaluation:
        """Evaluate diff against all policy rules."""
        findings = []

        # BLOCK: Prohibited writes
        if diff.new_prohibited_writes > 0:
            findings.append(
                Finding(
                    id="prohibited_writes",
                    severity="BLOCK",
                    rule="write_prohibited_zone_count > 0",
                    evidence=f"{diff.new_prohibited_writes} new writes to prohibited zones detected",
                    recommendation="Remove all writes to .intent/constitution/ and .intent/META/",
                    links=[],
                )
            )

        # HIGH: Subprocess delta
        subprocess_threshold = self.thresholds.get("subprocess_delta", 2)
        if "subprocess" in diff.by_type:
            subprocess_delta = diff.by_type["subprocess"].delta
            if subprocess_delta > subprocess_threshold:
                findings.append(
                    Finding(
                        id="subprocess_increase",
                        severity="HIGH",
                        rule=f"subprocess delta > +{subprocess_threshold}",
                        evidence=f"Subprocess calls increased by {subprocess_delta}",
                        recommendation="Audit new subprocess usage for sandboxing and security",
                        links=[],
                    )
                )

        # HIGH: Network delta
        network_threshold = self.thresholds.get("network_delta", 2)
        if "network" in diff.by_type:
            network_delta = diff.by_type["network"].delta
            if network_delta > network_threshold:
                findings.append(
                    Finding(
                        id="network_increase",
                        severity="HIGH",
                        rule=f"network delta > +{network_threshold}",
                        evidence=f"Network calls increased by {network_delta}",
                        recommendation="Review new network access for security and error handling",
                        links=[],
                    )
                )

        # MEDIUM: Mind lane drift
        mind_threshold_pct = self.thresholds.get("mind_lane_drift_percent", 20)
        if "mind" in diff.by_lane:
            mind_delta = diff.by_lane["mind"]
            if (
                mind_delta.percent_change
                and mind_delta.percent_change > mind_threshold_pct
            ):
                findings.append(
                    Finding(
                        id="mind_layer_drift",
                        severity="MEDIUM",
                        rule=f"mind lane writes delta > +{mind_threshold_pct}%",
                        evidence=f"Mind layer mutations increased {mind_delta.percent_change:.1f}%",
                        recommendation="Mind layer should have minimal mutation - investigate architectural drift",
                        links=[],
                    )
                )

        # MEDIUM: Production writes delta
        prod_threshold_pct = self.thresholds.get("production_writes_delta_percent", 10)
        if (
            diff.write_production.percent_change
            and diff.write_production.percent_change > prod_threshold_pct
        ):
            findings.append(
                Finding(
                    id="production_writes_increase",
                    severity="MEDIUM",
                    rule=f"production writes delta > +{prod_threshold_pct}%",
                    evidence=f"Production writes increased {diff.write_production.percent_change:.1f}%",
                    recommendation="Review new production write patterns for governance compliance",
                    links=[],
                )
            )

        # LOW: Hotspot mutations
        hotspot_threshold = self.thresholds.get("hotspot_mutation_count", 15)
        for hotspot in diff.hotspots_added:
            if hotspot.new_count and hotspot.new_count > hotspot_threshold:
                findings.append(
                    Finding(
                        id=f"hotspot_{hotspot.path}",
                        severity="LOW",
                        rule=f"new hotspot mutation_count > {hotspot_threshold}",
                        evidence=f"New hotspot {hotspot.path} has {hotspot.new_count} mutations",
                        recommendation="Consider refactoring to reduce mutation density",
                        links=[hotspot.path],
                    )
                )

        # Compute counts
        evaluation = PolicyEvaluation(findings=findings)
        for finding in findings:
            if finding.severity == "BLOCK":
                evaluation.blocking_count += 1
            elif finding.severity == "HIGH":
                evaluation.high_count += 1
            elif finding.severity == "MEDIUM":
                evaluation.medium_count += 1
            elif finding.severity == "LOW":
                evaluation.low_count += 1

        return evaluation
