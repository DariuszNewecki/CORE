# src/features/autonomy/audit_analyzer.py
"""
Audit Analyzer - Identifies auto-fixable violations from audit findings.

This service bridges the gap between audit detection and autonomous remediation
by analyzing audit findings and determining which ones can be automatically fixed
within constitutional bounds.

Constitutional alignment:
- Operates in micro_proposals autonomy lane only
- Respects safe_paths and forbidden_paths
- No mutations - pure analysis only
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

# REFACTORED: Removed direct settings import
from shared.logger import getLogger


logger = getLogger(__name__)


@dataclass
# ID: dc64f3c1-b122-4032-ac7c-acf00f43f6d6
class AutoFixablePattern:
    """Mapping between audit finding patterns and autonomous actions."""

    check_id_pattern: str  # Rule/check ID from audit finding
    action_handler: str  # Action that can fix this violation
    confidence: float  # How confident we are this will work (0.0-1.0)
    risk_level: str  # "low", "medium", "high"
    description: str  # Human-readable explanation


# ID: b2c3d4e5-f6a7-8901-bcde-f12345678901
class AuditAnalyzer:
    """
    Analyzes audit findings to identify auto-fixable violations.

    This is the first step in the autonomous loop trigger mechanism:
    audit findings → auto-fixable list → proposals → execution
    """

    # Mapping of known auto-fixable patterns
    # Start conservative - only include high-confidence, low-risk fixes
    FIXABLE_PATTERNS: ClassVar[list[AutoFixablePattern]] = [
        # Missing IDs (highest confidence, lowest risk)
        AutoFixablePattern(
            check_id_pattern="purity.stable_id_anchor",
            action_handler="autonomy.self_healing.add_ids",
            confidence=0.95,
            risk_level="low",
            description="Add missing capability IDs to functions/classes",
        ),
        # Code formatting (high confidence, low risk)
        AutoFixablePattern(
            check_id_pattern="code_standards.max_line_length",
            action_handler="autonomy.self_healing.fix_line_length",
            confidence=0.90,
            risk_level="low",
            description="Fix lines exceeding length limit",
        ),
        # Import sorting (high confidence, low risk)
        AutoFixablePattern(
            check_id_pattern="style.import_order",
            action_handler="autonomy.self_healing.sort_imports",
            confidence=0.90,
            risk_level="low",
            description="Sort imports according to style policy",
        ),
        # Unused imports (high confidence, low risk)
        AutoFixablePattern(
            check_id_pattern="style.no_unused_imports",
            action_handler="autonomy.self_healing.fix_imports",
            confidence=0.85,
            risk_level="low",
            description="Remove unused imports",
        ),
        # Code formatting (high confidence, low risk)
        AutoFixablePattern(
            check_id_pattern="style.formatter_required",
            action_handler="autonomy.self_healing.format_code",
            confidence=0.90,
            risk_level="low",
            description="Auto-format code with Black/Ruff",
        ),
        # File headers (high confidence, low risk)
        AutoFixablePattern(
            check_id_pattern="layout.src_module_header",
            action_handler="autonomy.self_healing.fix_headers",
            confidence=0.85,
            risk_level="low",
            description="Add or fix file headers",
        ),
        # Missing docstrings (medium confidence, low risk)
        AutoFixablePattern(
            check_id_pattern="caps.no_placeholder_text",
            action_handler="autonomy.self_healing.fix_docstrings",
            confidence=0.75,
            risk_level="low",
            description="Add missing docstrings",
        ),
        # Dead code removal (medium confidence, medium risk)
        AutoFixablePattern(
            check_id_pattern="code.dead_code",
            action_handler="autonomy.self_healing.remove_dead_code",
            confidence=0.70,
            risk_level="medium",
            description="Remove unreachable code",
        ),
    ]

    def __init__(self, repo_root: Path):
        """
        Initialize analyzer.

        Args:
            repo_root: Repository root path (defaults to context.git_service.repo_path)
        """
        self.repo_root = repo_root
        self.findings_path = self.repo_root / "reports" / "audit_findings.json"

    # ID: c3d4e5f6-a7b8-9012-cdef-123456789012
    def analyze_findings(self, findings_path: Path | None = None) -> dict[str, Any]:
        """
        Analyze audit findings to identify auto-fixable violations.

        Args:
            findings_path: Path to audit findings JSON (defaults to standard location)

        Returns:
            Analysis results with auto-fixable findings grouped by action
        """
        path = findings_path or self.findings_path

        if not path.exists():
            logger.warning("Audit findings not found: %s", path)
            return {
                "status": "no_findings",
                "message": f"No audit findings found at {path}",
                "auto_fixable_count": 0,
                "fixable_by_action": {},
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
            }

        logger.info("Analyzing %d audit findings", len(findings))

        # Group findings by fixable action
        fixable_by_action: dict[str, list[dict[str, Any]]] = {}
        not_fixable: list[dict[str, Any]] = []

        for finding in findings:
            check_id = finding.get("check_id", "") or finding.get("rule_id", "")

            if not check_id:
                continue

            # Find matching pattern
            pattern = self._find_matching_pattern(check_id)

            if pattern:
                action = pattern.action_handler
                if action not in fixable_by_action:
                    fixable_by_action[action] = []

                # Enrich finding with fix metadata
                enriched = {
                    **finding,
                    "fix_action": action,
                    "fix_confidence": pattern.confidence,
                    "fix_risk": pattern.risk_level,
                    "fix_description": pattern.description,
                }
                fixable_by_action[action].append(enriched)
            else:
                not_fixable.append(finding)

        total_fixable = sum(len(items) for items in fixable_by_action.values())

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
            "not_fixable": not_fixable[:20],  # Sample of non-fixable for analysis
            "summary_by_action": self._summarize_by_action(fixable_by_action),
        }

    # ID: d4e5f6a7-b8c9-0123-def1-234567890123
    def _find_matching_pattern(self, check_id: str) -> AutoFixablePattern | None:
        """
        Find the auto-fixable pattern that matches this check_id.

        Args:
            check_id: Check ID from audit finding

        Returns:
            Matching pattern or None
        """
        # Exact match first
        for pattern in self.FIXABLE_PATTERNS:
            if pattern.check_id_pattern == check_id:
                return pattern

        # Prefix match (e.g., "style.*" matches "style.linter_required")
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
        """
        Create a summary of fixable findings grouped by action.

        Args:
            fixable_by_action: Findings grouped by action handler

        Returns:
            List of summaries for each action
        """
        summaries = []

        for action, findings in sorted(fixable_by_action.items()):
            if not findings:
                continue

            # Get metadata from first finding (all should have same action)
            first = findings[0]

            # Count affected files
            affected_files = set()
            for f in findings:
                file_path = f.get("file_path") or f.get("file")
                if file_path:
                    affected_files.add(file_path)

            summaries.append(
                {
                    "action": action,
                    "finding_count": len(findings),
                    "affected_files": len(affected_files),
                    "confidence": first.get("fix_confidence", 0.0),
                    "risk_level": first.get("fix_risk", "unknown"),
                    "description": first.get("fix_description", ""),
                    "sample_files": sorted(affected_files)[:5],  # First 5 files
                }
            )

        # Sort by finding count (most violations first)
        summaries.sort(key=lambda x: x["finding_count"], reverse=True)

        return summaries


# ID: f6a7b8c9-d0e1-2345-f123-456789012345
def analyze_audit_findings(
    findings_path: Path | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """
    Convenience function to analyze audit findings.

    Args:
        findings_path: Path to audit findings JSON
        repo_root: Repository root path

    Returns:
        Analysis results
    """
    analyzer = AuditAnalyzer(repo_root=repo_root)
    return analyzer.analyze_findings(findings_path=findings_path)
