#!/usr/bin/env python3
"""
Emit latest audit evidence for governance verification.

Purpose
-------
Convert existing CORE audit artifacts (reports/audit_findings*.json) into a
stable evidence file used by the Enforcement Coverage Map verifier:

    reports/audit/latest_audit.json

This is deliberately conservative:
- It does NOT infer executed checks beyond what is present in findings artifacts.
- It does NOT introspect code or registries.
- It never over-claims.

Operational usage (no integration required):
1) core-admin check audit
2) python scripts/emit_latest_audit_evidence.py
3) python scripts/generate_enforcement_coverage_map.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]

REPORTS_DIR = REPO_ROOT / "reports"
AUDIT_DIR = REPORTS_DIR / "audit"

FINDINGS_PROCESSED = REPORTS_DIR / "audit_findings.processed.json"
FINDINGS_RAW = REPORTS_DIR / "audit_findings.json"

LATEST_EVIDENCE = AUDIT_DIR / "latest_audit.json"


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _extract_check_ids(payload: Any) -> set[str]:
    """
    Extract check identifiers from a findings payload.

    We are schema-agnostic by intent and accept common shapes:
      - List[Dict] of findings
      - Dict with a 'findings' field that is a list
    """
    findings: list[dict[str, Any]] = []

    if isinstance(payload, list):
        findings = [x for x in payload if isinstance(x, dict)]
    elif isinstance(payload, dict):
        raw = payload.get("findings")
        if isinstance(raw, list):
            findings = [x for x in raw if isinstance(x, dict)]

    check_ids: set[str] = set()

    for f in findings:
        # Most preferred field name
        val = f.get("check_id")
        if isinstance(val, str) and val.strip():
            check_ids.add(val.strip())
            continue

        # Fallbacks (some systems encode rule id / policy id instead)
        for alt in ("rule_id", "policy_id", "id"):
            alt_val = f.get(alt)
            if isinstance(alt_val, str) and alt_val.strip():
                check_ids.add(alt_val.strip())
                break

    return check_ids


def main() -> int:
    source_path: Path | None = None
    if FINDINGS_PROCESSED.exists():
        source_path = FINDINGS_PROCESSED
    elif FINDINGS_RAW.exists():
        source_path = FINDINGS_RAW

    if source_path is None:
        raise FileNotFoundError(
            "No audit findings found. Expected one of:\n"
            f" - {FINDINGS_PROCESSED}\n"
            f" - {FINDINGS_RAW}\n\n"
            "Run 'core-admin check audit' first."
        )

    payload = _load_json(source_path)
    executed_checks = sorted(_extract_check_ids(payload))

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    evidence = {
        "schema_version": "0.1.0",
        "generated_at_utc": _utc_now(),
        "source": str(source_path.relative_to(REPO_ROOT)),
        "source_mtime_utc": datetime.fromtimestamp(
            source_path.stat().st_mtime, tz=UTC
        ).strftime("%Y-%m-%dT%H:%M:%SZ"),
        # Conservative definition: "executed checks we have evidence for"
        "executed_checks": executed_checks,
        "counts": {
            "executed_checks": len(executed_checks),
        },
    }

    with LATEST_EVIDENCE.open("w", encoding="utf-8") as fh:
        json.dump(evidence, fh, indent=2)

    print("[OK] Wrote audit evidence")
    print(f" - Source : {evidence['source']}")
    print(f" - Output : {LATEST_EVIDENCE}")
    print(f" - Checks : {evidence['counts']['executed_checks']} (conservative)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
