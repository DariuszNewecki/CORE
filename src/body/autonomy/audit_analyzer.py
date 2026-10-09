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

from pathlib import Path
from typing import Any

import yaml

from shared.logger import getLogger
from shared.path_resolver import PathResolver


logger = getLogger(__name__)

# Fallback used only when governance_paths.yaml cannot be loaded.
# This constant must NOT be used in logic — it is a last-resort default only.
_FALLBACK_MIN_CONFIDENCE: float = 0.80


# ID: 67cbf053-dc90-430d-9963-2fc312084417
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
    Each entry must declare exactly one of 'action' (AtomicAction id) or
    'flow' (Flow id). The validated dict carries both 'ref_id' and 'ref_kind'
    so callers can construct the appropriate ProposalAction without
    re-discriminating.
    Returns a dict of
      {check_id: {action, flow, ref_id, ref_kind, confidence, description, status}}.
    Fails gracefully — returns empty dict if file missing or malformed.

    Note (#582): the per-entry `risk:` field in auto_remediation.yaml was
    removed; the authoritative source for action risk is
    .intent/enforcement/config/action_risk.yaml (impact_level), consumed by
    ActionRegistry and used by Proposal.compute_risk(). Prior versions of
    this loader read `risk:` and attached it as `fix_risk` to findings —
    grep confirmed nothing downstream consumed that field.
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

        has_action = entry.get("action") is not None
        has_flow = entry.get("flow") is not None
        if has_action and has_flow:
            logger.warning(
                "Remediation map: entry '%s' declares both 'action' and 'flow' — "
                "skipped (must declare exactly one)",
                check_id,
            )
            continue
        if not has_action and not has_flow:
            logger.warning(
                "Remediation map: entry '%s' missing both 'action' and 'flow' — "
                "skipped (must declare exactly one)",
                check_id,
            )
            continue
        # Skip PENDING entries explicitly (status field in auto_remediation.yaml)
        if entry.get("status") == "PENDING":
            logger.debug("Remediation map: skipping PENDING entry '%s'", check_id)
            continue

        ref_id = entry["action"] if has_action else entry["flow"]
        ref_kind = "action" if has_action else "flow"

        validated[check_id] = {
            "action": entry.get("action"),
            "flow": entry.get("flow"),
            "ref_id": ref_id,
            "ref_kind": ref_kind,
            "confidence": float(entry.get("confidence", 0.0)),
            "description": entry.get("description", ""),
            "status": entry.get("status", "ACTIVE"),
        }

    logger.debug(
        "Remediation map loaded: %d active mappings from %s", len(validated), map_path
    )
    return validated


# ID: b4269730-f061-4c47-9b4a-10df7b2ba147
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
