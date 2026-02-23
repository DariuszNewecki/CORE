# src/body/cli/logic/governance/traceability_service.py
# ID: 7f8a9b0c-1d2e-3f4a-5b6c-7d8e9f0a1b2c

"""
Governance Traceability Service - Phase 3 Hardening.
Produces a detailed mapping of Constitutional Law to physical Enforcement Engines.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shared.logger import getLogger

from .engine import generate_coverage_map


logger = getLogger(__name__)


# ID: 722fc9bd-1796-40e2-960e-5fadf75104cb
class GovernanceTraceabilityService:
    """
    Analyzes the gap between declared law and physical enforcement.
    """

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.report_dir = repo_root / "reports" / "governance"
        self.report_dir.mkdir(parents=True, exist_ok=True)

    # ID: d5e39414-301c-4f9a-8381-52caea6bd50e
    def generate_traceability_report(self) -> dict[str, Any]:
        """
        Calculates the binding state of all constitutional rules.
        """
        # Reuse your existing high-fidelity mapping engine
        coverage_data = generate_coverage_map(self.repo_root)

        unbound_rules = []
        enforced_rules = []

        for entry in coverage_data.get("entries", []):
            rule = entry["rule"]
            status = entry["coverage_status"]

            rule_info = {
                "id": rule["rule_id"],
                "policy": rule["policy"],
                "engine": rule.get("check_engine") or "NONE",
                "severity": rule["severity"],
            }

            if status == "declared_only":
                unbound_rules.append(rule_info)
            else:
                enforced_rules.append(rule_info)

        report = {
            "summary": {
                "total_rules": len(coverage_data["entries"]),
                "enforced_count": len(enforced_rules),
                "unbound_count": len(unbound_rules),
                "coverage_percent": coverage_data["summary"]["execution_rate"],
            },
            "critical_gaps": [r for r in unbound_rules if r["severity"] == "error"],
            "unbound_rules": unbound_rules,
        }

        # Persist as a formal evidence artifact
        output_path = self.report_dir / "traceability_matrix.json"
        output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

        return report
