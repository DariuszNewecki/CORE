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

V2.7 FIX:
- Removed hardcoded REMEDIATION_MAP_PATH constant.
- Removed hardcoded MIN_CONFIDENCE constant.
- Both are now loaded via PathResolver from:
    .intent/enforcement/config/governance_paths.yaml
- AuditAnalyzer.findings_path now uses PathResolver.audit_findings_path.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from shared.logger import getLogger
from shared.path_resolver import PathResolver


logger = getLogger(__name__)

# Fallback used only when governance_paths.yaml cannot be loaded.
# This constant must NOT be used in logic — it is a last-resort default only.
_FALLBACK_MIN_CONFIDENCE: float = 0.80


# ID: e1f2a3b4-c5d6-7890-efab-cd0000000001
def _load_governance_config(path_resolver: PathResolver) -> dict[str, Any]:
    """
    Load governance paths & thresholds from .intent/enforcement/config/governance_paths.yaml.

    Returns empty dict on failure so callers can apply fallbacks gracefully.
    """
    config_path = path_resolver.governance_config_path
    if not config_path.exists():
        logger.warning(
            "Governance config not found at %s — using fallback defaults. "
            "Create .intent/enforcement/config/governance_paths.yaml to configure.",
            config_path,
        )
        return {}
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception as e:
        logger.error("Failed to load governance config from %s: %s", config_path, e)
        return {}


# ID: dc64f3c1-b122-4032-ac7c-acf00f43f6d6
def _load_remediation_map(path_resolver: PathResolver) -> dict[str, dict[str, Any]]:
    """
    Load the remediation map via PathResolver.

    Path is resolved from PathResolver.remediation_map_path — never hardcoded.
    Returns a dict of {check_id: {action, confidence, risk, description}}.
    Fails gracefully — returns empty dict if file missing or malformed.
    """
    map_path = path_resolver.remediation_map_path

    if not map_path.exists():
        logger.warning(
            "Remediation map not found: %s — no autonomous proposals will be generated. "
            "Populate .intent/enforcement/mappings/remediation/auto_remediation.yaml to enable.",
            map_path,
        )
        return {}

    try:
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
                "Remediation map: entry '%s' missing 'action' field — skipped", check_id
            )
            continue
        # Skip PENDING entries explicitly (status field in auto_remediation.yaml)
        if entry.get("status") == "PENDING":
            logger.debug("Remediation map: skipping PENDING entry '%s'", check_id)
            continue
        validated[check_id] = {
            "action": entry["action"],
            "confidence": float(entry.get("confidence", 0.0)),
            "risk": entry.get("risk", "medium"),
            "description": entry.get("description", ""),
            "status": entry.get("status", "ACTIVE"),
        }

    logger.debug(
        "Remediation map loaded: %d active mappings from %s", len(validated), map_path
    )
    return validated


# ID: b2c3d4e5-f6a7-8901-bcde-f12345678901
class AuditAnalyzer:
    """
    Analyzes audit findings to identify auto-fixable violations.

    Autonomous loop: audit findings -> fixable list -> proposals -> execution.

    The mapping from check_id to action is loaded from:
      .intent/enforcement/mappings/remediation/auto_remediation.yaml

    The min_confidence threshold is loaded from:
      .intent/enforcement/config/governance_paths.yaml

    No paths or thresholds are hardcoded in this file.
    Adding a new remediable rule = editing .intent/ only.
    """

    def __init__(self, repo_root: Path) -> None:
        """
        Initialize analyzer.

        Args:
            repo_root: Repository root path. Used to construct PathResolver.
                       Kept as a Path argument for backward compatibility with
                       all existing callers.
        """
        self._path_resolver = PathResolver(repo_root)

        # Derive findings path from PathResolver — never hardcoded.
        self.findings_path = self._path_resolver.audit_findings_path

        # Load min_confidence from constitutional governance config.
        gov_config = _load_governance_config(self._path_resolver)
        self._min_confidence: float = float(
            gov_config.get("remediation", {}).get(
                "min_confidence", _FALLBACK_MIN_CONFIDENCE
            )
        )
        logger.debug(
            "AuditAnalyzer: min_confidence=%.2f (source: %s)",
            self._min_confidence,
            "governance_paths.yaml" if gov_config else "fallback default",
        )

        self._remediation_map: dict[str, dict[str, Any]] | None = None

    def _get_remediation_map(self) -> dict[str, dict[str, Any]]:
        """Lazy-load the remediation map (cached per instance)."""
        if self._remediation_map is None:
            self._remediation_map = _load_remediation_map(self._path_resolver)
        return self._remediation_map

    # ID: c3d4e5f6-a7b8-9012-cdef-123456789012
    def analyze_findings(self, findings_path: Path | None = None) -> dict[str, Any]:
        """
        Analyze audit findings to identify auto-fixable violations.

        Loads the remediation map from .intent/, reads audit findings,
        matches each finding's check_id against the map, and groups
        fixable findings by action. Only entries with confidence >=
        min_confidence (from governance_paths.yaml) are included.

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
                    "Populate .intent/enforcement/mappings/remediation/auto_remediation.yaml."
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
                "Unexpected findings format: expected list, got %s",
                type(findings),
            )
            return {
                "status": "format_error",
                "message": "Audit findings not in expected format",
                "auto_fixable_count": 0,
                "fixable_by_action": {},
                "summary_by_action": [],
            }

        logger.info(
            "Analyzing %d audit findings against %d remediation mappings "
            "(min_confidence=%.2f)",
            len(findings),
            len(remediation_map),
            self._min_confidence,
        )

        fixable_by_action: dict[str, list[dict[str, Any]]] = {}
        not_fixable: list[dict[str, Any]] = []

        for finding in findings:
            check_id = finding.get("check_id", "") or finding.get("rule_id", "")
            if not check_id:
                continue

            entry = remediation_map.get(check_id)

            if entry and entry["confidence"] >= self._min_confidence:
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
        return [
            {
                "action": action,
                "count": len(findings),
                "files": list({f.get("file_path", "unknown") for f in findings})[:10],
                "avg_confidence": (
                    sum(f["fix_confidence"] for f in findings) / len(findings)
                    if findings
                    else 0.0
                ),
            }
            for action, findings in sorted(
                fixable_by_action.items(), key=lambda kv: len(kv[1]), reverse=True
            )
        ]
