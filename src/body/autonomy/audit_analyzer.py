# src/body/autonomy/audit_analyzer.py
"""
Audit Analyzer - Identifies auto-fixable violations from audit findings.

This service bridges the gap between audit detection and autonomous remediation
by analyzing audit findings and determining which ones can be automatically fixed
within constitutional bounds.

Constitutional alignment:
- Operates in micro_proposals autonomy lane only
- Respects safe_paths and forbidden_paths
- No mutations - pure analysis only

FIXABLE_PATTERNS maps audit check IDs to registered atomic action IDs.
All action_handler values are verified against the live action registry.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from shared.logger import getLogger


logger = getLogger(__name__)

# Minimum confidence required to generate a proposal.
# Below this threshold the action is too uncertain to propose autonomously.
MIN_CONFIDENCE: float = 0.80


@dataclass
# ID: dc64f3c1-b122-4032-ac7c-acf00f43f6d6
class AutoFixablePattern:
    """Mapping between audit finding patterns and registered atomic actions."""

    check_id_pattern: str  # Rule/check ID from audit finding (exact or prefix*)
    action_handler: str  # Registered atomic action ID (verified against registry)
    confidence: float  # 0.0-1.0 - below MIN_CONFIDENCE proposals are skipped
    risk_level: str  # "low" | "medium" | "high"
    description: str  # Human-readable explanation


# ID: b2c3d4e5-f6a7-8901-bcde-f12345678901
class AuditAnalyzer:
    """
    Analyzes audit findings to identify auto-fixable violations.

    Autonomous loop: audit findings → fixable list → proposals → execution.

    FIXABLE_PATTERNS uses only action IDs that exist in the live registry.
    Verified set (from body/atomic/actions.py registrations):
      fix.format, fix.imports, fix.headers, fix.ids, fix.duplicate_ids,
      fix.logging, fix.placeholders, fix.atomic_actions, fix.docstrings
    """

    FIXABLE_PATTERNS: ClassVar[list[AutoFixablePattern]] = [
        # Missing stable ID anchors → fix.ids
        AutoFixablePattern(
            check_id_pattern="purity.stable_id_anchor",
            action_handler="fix.ids",
            confidence=0.95,
            risk_level="low",
            description="Add missing # ID: anchors to public symbols",
        ),
        # print() / console.print() violations → fix.logging
        AutoFixablePattern(
            check_id_pattern="logic.logging.standard_only",
            action_handler="fix.logging",
            confidence=0.90,
            risk_level="low",
            description="Replace print() calls with logger",
        ),
        # Import order / unused imports → fix.imports
        AutoFixablePattern(
            check_id_pattern="style.import_order",
            action_handler="fix.imports",
            confidence=0.90,
            risk_level="low",
            description="Sort imports according to style policy",
        ),
        AutoFixablePattern(
            check_id_pattern="style.no_unused_imports",
            action_handler="fix.imports",
            confidence=0.85,
            risk_level="low",
            description="Remove unused imports",
        ),
        # Code formatting → fix.format
        AutoFixablePattern(
            check_id_pattern="style.formatter_required",
            action_handler="fix.format",
            confidence=0.90,
            risk_level="low",
            description="Auto-format code with Black/Ruff",
        ),
        # File headers → fix.headers
        AutoFixablePattern(
            check_id_pattern="layout.src_module_header",
            action_handler="fix.headers",
            confidence=0.85,
            risk_level="low",
            description="Add or fix constitutional file headers",
        ),
        # Placeholder docstrings → fix.docstrings
        AutoFixablePattern(
            check_id_pattern="purity.docstrings.required",
            action_handler="fix.docstrings",
            confidence=0.80,
            risk_level="low",
            description="Add missing docstrings to public symbols",
        ),
        AutoFixablePattern(
            check_id_pattern="caps.no_placeholder_text",
            action_handler="fix.docstrings",
            confidence=0.80,
            risk_level="low",
            description="Replace placeholder docstrings with real ones",
        ),
        # Duplicate symbol IDs → fix.duplicate_ids
        AutoFixablePattern(
            check_id_pattern="linkage.duplicate_ids",
            action_handler="fix.duplicate_ids",
            confidence=0.85,
            risk_level="low",
            description="Resolve duplicate # ID: anchors",
        ),
    ]

    def __init__(self, repo_root: Path) -> None:
        """
        Initialize analyzer.

        Args:
            repo_root: Repository root path
        """
        self.repo_root = repo_root
        self.findings_path = self.repo_root / "reports" / "audit_findings.json"

    # ID: c3d4e5f6-a7b8-9012-cdef-123456789012
    def analyze_findings(self, findings_path: Path | None = None) -> dict[str, Any]:
        """
        Analyze audit findings to identify auto-fixable violations.

        Only patterns with confidence >= MIN_CONFIDENCE are included.

        Args:
            findings_path: Override path to audit findings JSON.

        Returns:
            Dict with keys: status, total_findings, auto_fixable_count,
            fixable_by_action, not_fixable, summary_by_action.
        """
        path = findings_path or self.findings_path

        if not path.exists():
            logger.warning("Audit findings not found: %s", path)
            return {
                "status": "no_findings",
                "message": f"No audit findings found at {path}",
                "auto_fixable_count": 0,
                "fixable_by_action": {},
                "summary_by_action": [],
            }

        try:
            with open(path, encoding="utf-8") as f:
                findings = json.load(f)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse audit findings: %s", e)
            return {
                "status": "parse_error",
                "message": f"Failed to parse JSON: {e}",
                "auto_fixable_count": 0,
                "fixable_by_action": {},
                "summary_by_action": [],
            }

        if not isinstance(findings, list):
            logger.error(
                "Unexpected findings format: expected list, got %s", type(findings)
            )
            return {
                "status": "format_error",
                "message": "Audit findings not in expected format",
                "auto_fixable_count": 0,
                "fixable_by_action": {},
                "summary_by_action": [],
            }

        logger.info("Analyzing %d audit findings", len(findings))

        fixable_by_action: dict[str, list[dict[str, Any]]] = {}
        not_fixable: list[dict[str, Any]] = []

        for finding in findings:
            check_id = finding.get("check_id", "") or finding.get("rule_id", "")
            if not check_id:
                continue

            pattern = self._find_matching_pattern(check_id)

            if pattern and pattern.confidence >= MIN_CONFIDENCE:
                action = pattern.action_handler
                fixable_by_action.setdefault(action, [])
                fixable_by_action[action].append(
                    {
                        **finding,
                        "fix_action": action,
                        "fix_confidence": pattern.confidence,
                        "fix_risk": pattern.risk_level,
                        "fix_description": pattern.description,
                    }
                )
            else:
                not_fixable.append(finding)

        total_fixable = sum(len(v) for v in fixable_by_action.values())

        logger.info(
            "Analysis complete: %d auto-fixable (%.1f%%), %d not auto-fixable",
            total_fixable,
            (total_fixable / len(findings) * 100) if findings else 0,
            len(not_fixable),
        )

        return {
            "status": "success",
            "total_findings": len(findings),
            "auto_fixable_count": total_fixable,
            "not_fixable_count": len(not_fixable),
            "fixable_by_action": fixable_by_action,
            "not_fixable": not_fixable[:20],
            "summary_by_action": self._summarize_by_action(fixable_by_action),
        }

    # ID: d4e5f6a7-b8c9-0123-def1-234567890123
    def _find_matching_pattern(self, check_id: str) -> AutoFixablePattern | None:
        """Find the pattern that matches this check_id (exact first, then prefix)."""
        for pattern in self.FIXABLE_PATTERNS:
            if pattern.check_id_pattern == check_id:
                return pattern
        for pattern in self.FIXABLE_PATTERNS:
            if pattern.check_id_pattern.endswith("*"):
                prefix = pattern.check_id_pattern[:-1]
                if check_id.startswith(prefix):
                    return pattern
        return None

    # ID: e5f6a7b8-c9d0-1234-ef12-345678901234
    def _summarize_by_action(
        self, fixable_by_action: dict[str, list[dict[str, Any]]]
    ) -> list[dict[str, Any]]:
        """Summarise fixable findings grouped by action for logging/reporting."""
        summaries = []
        for action, findings in sorted(fixable_by_action.items()):
            if not findings:
                continue
            first = findings[0]
            affected_files: set[str] = set()
            for f in findings:
                fp = f.get("file_path") or f.get("file")
                if fp:
                    affected_files.add(fp)
            summaries.append(
                {
                    "action": action,
                    "finding_count": len(findings),
                    "affected_files": len(affected_files),
                    "confidence": first.get("fix_confidence", 0.0),
                    "risk_level": first.get("fix_risk", "unknown"),
                    "description": first.get("fix_description", ""),
                    "sample_files": sorted(affected_files)[:5],
                }
            )
        summaries.sort(key=lambda x: x["finding_count"], reverse=True)
        return summaries


# ID: f6a7b8c9-d0e1-2345-f123-456789012345
def analyze_audit_findings(
    findings_path: Path | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Convenience wrapper for AuditAnalyzer.analyze_findings()."""
    if repo_root is None:
        from shared.config import settings

        repo_root = settings.REPO_PATH
    analyzer = AuditAnalyzer(repo_root=repo_root)
    return analyzer.analyze_findings(findings_path=findings_path)
