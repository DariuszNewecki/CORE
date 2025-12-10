# src/mind/enforcement/guard.py

"""
Intent: Governance/validation guard commands exposed to the operator.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from shared.logger import getLogger


logger = getLogger(__name__)


def _find_manifest_path(root: Path, explicit: Path | None) -> Path | None:
    """Locate and return the path to the project manifest file, or None."""
    if explicit and explicit.exists():
        return explicit
    for p in (root / ".intent/project_manifest.yaml", root / ".intent/manifest.yaml"):
        if p.exists():
            return p
    return None


def _load_raw_manifest(root: Path, explicit: Path | None) -> dict[str, Any]:
    """Loads and parses a YAML manifest file, returning an empty dict if not found."""
    path = _find_manifest_path(root, explicit)
    if not path:
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data


def _ux_defaults(root: Path, explicit: Path | None) -> dict[str, Any]:
    """Extracts and returns UX-related default values from the manifest."""
    raw = _load_raw_manifest(root, explicit)
    ux = raw.get("operator_experience", {}).get("guard", {}).get("drift", {})
    return {
        "default_format": ux.get("default_format", "json"),
        "default_fail_on": ux.get("default_fail_on", "any"),
        "strict_default": bool(ux.get("strict_default", False)),
        "evidence_json": bool(ux.get("evidence_json", True)),
        "evidence_path": ux.get("evidence_path", "reports/drift_report.json"),
        "labels": ux.get(
            "labels",
            {
                "none": "NONE",
                "success": "✅ No capability drift",
                "failure": "🚨 Drift detected",
            },
        ),
    }


def _is_clean(report: dict) -> bool:
    """Determines if a report is clean."""
    return not (
        report.get("missing_in_code")
        or report.get("undeclared_in_manifest")
        or report.get("mismatched_mappings")
    )


def _format_report(report_dict: dict, labels: dict[str, str]) -> dict[str, Any]:
    """Formats a drift report into a structured dictionary for logging or serialization."""
    formatted = {
        "missing_in_code": report_dict.get("missing_in_code", []),
        "undeclared_in_manifest": report_dict.get("undeclared_in_manifest", []),
        "mismatched_mappings": report_dict.get("mismatched_mappings", []),
        "is_clean": _is_clean(report_dict),
        "status_label": (
            labels["success"] if _is_clean(report_dict) else labels["failure"]
        ),
    }
    return formatted


def _print_pretty(report_dict: dict, labels: dict[str, str]) -> None:
    """Logs a structured summary of the drift report."""
    formatted = _format_report(report_dict, labels)
    if formatted["is_clean"]:
        logger.info("Capability drift check passed: %s", formatted["status_label"])
    else:
        logger.warning("Capability drift detected: %s", formatted["status_label"])
        if formatted["missing_in_code"]:
            logger.warning("Missing in code: %s", formatted["missing_in_code"])
        if formatted["undeclared_in_manifest"]:
            logger.warning(
                "Undeclared in manifest: %s", formatted["undeclared_in_manifest"]
            )
        if formatted["mismatched_mappings"]:
            logger.warning("Mismatched mappings: %s", formatted["mismatched_mappings"])
