# src/body/autonomy/audit_analyzer.py
"""
Audit Analyzer - Identifies auto-fixable violations from audit findings.

Bridges audit detection and autonomous remediation by reading the
constitutional remediation map from .intent/ and matching audit findings
against it.

Constitutional alignment:
- Remediation mappings live in .intent/enforcement/mappings/remediation/
- No action mappings are hardcoded in this file
- Adding/removing a mapping is a constitutional act (.intent/ edit only)
- No mutations - pure analysis only
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shared.logger import getLogger


logger = getLogger(__name__)

REMEDIATION_MAP_PATH = Path(
    ".intent/enforcement/mappings/remediation/auto_remediation.yaml"
)
MIN_CONFIDENCE: float = 0.80


# ID: dc64f3c1-b122-4032-ac7c-acf00f43f6d6
def _load_remediation_map(repo_root: Path) -> dict[str, dict[str, Any]]:
    """
    Load the remediation map from .intent/enforcement/mappings/remediation/.

    Returns a dict of {check_id: {action, confidence, risk, description}}.
    Fails gracefully - returns empty dict if file missing or malformed.
    """
    map_path = repo_root / REMEDIATION_MAP_PATH

    if not map_path.exists():
        logger.warning(
            "Remediation map not found: %s - no autonomous proposals will be generated. "
            "Create .intent/enforcement/mappings/remediation/auto_remediation.yaml to enable.",
            map_path,
        )
        return {}

    try:
        import yaml

        raw = yaml.safe_load(map_path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error("Failed to load remediation map from %s: %s", map_path, e)
        return {}

    mappings = raw.get("mappings", {})
    if not isinstance(mappings, dict):
        logger.error(
            "Remediation map has unexpected format (expected dict under 'mappings')"
        )
        return {}

    validated: dict[str, dict[str, Any]] = {}
    for check_id, entry in mappings.items():
        if not isinstance(entry, dict):
            logger.warning(
                "Remediation map: skipping malformed entry for '%s'", check_id
            )
            continue
        if "action" not in entry:
            logger.warning(
                "Remediation map: entry '%s' missing 'action' field - skipped", check_id
            )
            continue
        validated[check_id] = {
            "action": entry["action"],
            "confidence": float(entry.get("confidence", 0.0)),
            "risk": entry.get("risk", "medium"),
            "description": entry.get("description", ""),
        }

    logger.debug(
        "Remediation map loaded: %d mappings from %s", len(validated), map_path
    )
    return validated


# ID: b2c3d4e5-f6a7-8901-bcde-f12345678901
class AuditAnalyzer:
    """
    Analyzes audit findings to identify auto-fixable violations.

    Autonomous loop: audit findings -> fixable list -> proposals -> execution.

    The mapping from check_id to action is loaded from:
      .intent/enforcement/mappings/remediation/auto_remediation.yaml

    No hardcoded mappings. Adding a new remediable rule = editing .intent/ only.
    """

    def __init__(self, repo_root: Path) -> None:
        """
        Initialize analyzer.

        Args:
            repo_root: Repository root path
        """
        self.repo_root = repo_root
        self.findings_path = self.repo_root / "reports" / "audit_findings.json"
        self._remediation_map: dict[str, dict[str, Any]] | None = None

    def _get_remediation_map(self) -> dict[str, dict[str, Any]]:
        """Lazy-load the remediation map (cached per instance)."""
        if self._remediation_map is None:
            self._remediation_map = _load_remediation_map(self.repo_root)
        return self._remediation_map

    # ID: c3d4e5f6-a7b8-9012-cdef-123456789012
    def analyze_findings(self, findings_path: Path | None = None) -> dict[str, Any]:
        """
        Analyze audit findings to identify auto-fixable violations.

        Loads the remediation map from .intent/, reads audit findings,
        matches each finding's check_id against the map, and groups
        fixable findings by action. Only entries with confidence >=
        MIN_CONFIDENCE are included.

        Args:
            findings_path: Override path to audit findings JSON.

        Returns:
            Dict with keys: status, total_findings, auto_fixable_count,
            fixable_by_action, not_fixable, summary_by_action.
        """
        remediation_map = self._get_remediation_map()

        if not remediation_map:
            return {
                "status": "no_remediation_map",
                "message": (
                    "No remediation mappings found. "
                    "Create .intent/enforcement/mappings/remediation/auto_remediation.yaml."
                ),
                "auto_fixable_count": 0,
                "fixable_by_action": {},
                "summary_by_action": [],
            }

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

        logger.info(
            "Analyzing %d audit findings against %d remediation mappings",
            len(findings),
            len(remediation_map),
        )

        fixable_by_action: dict[str, list[dict[str, Any]]] = {}
        not_fixable: list[dict[str, Any]] = []

        for finding in findings:
            check_id = finding.get("check_id", "") or finding.get("rule_id", "")
            if not check_id:
                continue

            entry = remediation_map.get(check_id)

            if entry and entry["confidence"] >= MIN_CONFIDENCE:
                action = entry["action"]
                fixable_by_action.setdefault(action, [])
                fixable_by_action[action].append(
                    {
                        **finding,
                        "fix_action": action,
                        "fix_confidence": entry["confidence"],
                        "fix_risk": entry["risk"],
                        "fix_description": entry["description"],
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

    # ID: e5f6a7b8-c9d0-1234-ef12-345678901234
    def _summarize_by_action(
        self, fixable_by_action: dict[str, list[dict[str, Any]]]
    ) -> list[dict[str, Any]]:
        """Summarise fixable findings grouped by action."""
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
    """Convenience wrapper for AuditAnalyzer.analyze_findings().

    Args:
        findings_path: Override path to audit findings JSON.
        repo_root: Repository root path. Required — callers must supply this.

    Raises:
        ValueError: If repo_root is not provided.
    """
    if repo_root is None:
        raise ValueError(
            "analyze_audit_findings: repo_root is required. "
            "Pass settings.REPO_PATH from the calling layer."
        )
    analyzer = AuditAnalyzer(repo_root=repo_root)
    return analyzer.analyze_findings(findings_path=findings_path)
