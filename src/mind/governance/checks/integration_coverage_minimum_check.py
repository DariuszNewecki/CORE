# src/mind/governance/checks/integration_coverage_minimum_check.py
"""
Integration Coverage Minimum Governance Check

Enforces integration rule declared in standard_operations_general:
- integration.coverage_minimum

Intent:
CORE must enforce a minimum governance enforcement coverage threshold as a gating
integration requirement. If coverage is below the declared minimum, integrations
must not be considered acceptable.

Design constraints:
- Prefer policy-provided expectations (rule_data) first.
- Prefer internal CORE conventions (PathResolver policy resolution) before fallback scanning.
- Evidence-backed; do not pretend-pass when coverage artefacts cannot be discovered/parsed.
- Hardened against evolving EnforcementMethod._create_finding() signatures.
"""

from __future__ import annotations

import inspect
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

import yaml

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.rule_enforcement_check import (
    EnforcementMethod,
    RuleEnforcementCheck,
)
from shared.config import settings
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)

RULE_INTEGRATION_COVERAGE_MINIMUM = "integration.coverage_minimum"


def _create_finding_safe(method: EnforcementMethod, **kwargs: Any) -> AuditFinding:
    """
    EnforcementMethod._create_finding() signature varies across CORE versions.

    We only pass parameters supported by the runtime signature to prevent
    unexpected keyword argument errors (e.g., 'details', 'rule_id', etc.).
    """
    sig = inspect.signature(method._create_finding)  # type: ignore[attr-defined]
    allowed = set(sig.parameters.keys())
    filtered = {k: v for k, v in kwargs.items() if k in allowed}
    return method._create_finding(**filtered)  # type: ignore[attr-defined]


def _safe_load(path: Path) -> Any:
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _as_float(val: Any) -> float | None:
    try:
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return float(val)
        s = str(val).strip()
        if not s:
            return None
        return float(s)
    except Exception:
        return None


def _rel(repo_path: Path, p: Path) -> str:
    try:
        return str(p.relative_to(repo_path))
    except Exception:
        return str(p)


@dataclass(frozen=True)
class _CoverageSnapshot:
    """
    Normalized coverage stats.
    """

    enforced: int
    total: int
    enforcement_rate: float  # percentage in [0, 100]
    raw: dict[str, Any]
    source_path: str


def _extract_threshold(rule_data: dict[str, Any]) -> float | None:
    """
    Policy shapes tolerated (best-effort):
    - minimum_enforcement_rate: 75
    - minimum: 75
    - threshold: 75
    - min_percent: 75
    - percent: 75
    """
    for k in (
        "minimum_enforcement_rate",
        "minimum",
        "threshold",
        "min_percent",
        "percent",
        "coverage_minimum",
    ):
        v = _as_float(rule_data.get(k))
        if v is not None:
            return v
    return None


def _discover_coverage_map_files(repo_path: Path) -> list[Path]:
    """
    Conservative discovery across common CORE locations.

    We do NOT assume a single filename because this artifact may evolve.
    We prefer .intent-based artefacts, but also scan a few plausible output dirs.
    """
    candidates: list[Path] = []

    roots = [
        repo_path / ".intent",
        repo_path / "artifacts",
        repo_path / "reports",
        repo_path / ".cache",
        repo_path / ".tmp",
    ]

    needles = (
        "coverage_map",
        "enforcement_coverage",
        "governance_coverage",
        "coverage",
    )

    for root in roots:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix.lower() not in (".json", ".yaml", ".yml"):
                continue
            name = p.name.lower()
            if any(n in name for n in needles):
                candidates.append(p)

    # Deduplicate and sort newest-first (mtime)
    uniq = list({c.resolve() for c in candidates})
    uniq.sort(key=lambda x: x.stat().st_mtime if x.exists() else 0, reverse=True)
    return [Path(p) for p in uniq]


def _parse_coverage_snapshot(repo_path: Path, p: Path) -> _CoverageSnapshot | None:
    """
    Normalize a variety of coverage map shapes into a simple snapshot.

    Tolerated shapes (best-effort):
    - { totals: { total_rules: N, enforced: M, enforcement_rate: 43.1 } }
    - { total_rules: N, enforced: M, enforcement_rate: 43.1 }
    - { rules: [...], enforced_rule_ids: [...], ... }
    - { enforced: [...], declared_only: [...], ... } where lists represent rule ids
    """
    try:
        doc = _safe_load(p)
    except Exception as exc:
        logger.debug("IntegrationCoverageMinimum: failed parsing %s: %s", p, exc)
        return None

    raw: dict[str, Any] = doc if isinstance(doc, dict) else {"value": doc}

    enforced: int | None = None
    total: int | None = None
    rate: float | None = None

    # 1) totals section
    totals = raw.get("totals") if isinstance(raw, dict) else None
    if isinstance(totals, dict):
        total = (
            int(totals.get("total_rules"))
            if totals.get("total_rules") is not None
            else total
        )
        enforced = (
            int(totals.get("enforced"))
            if totals.get("enforced") is not None
            else enforced
        )
        rate = _as_float(totals.get("enforcement_rate")) if rate is None else rate

    # 2) top-level keys
    if isinstance(raw, dict):
        if total is None and raw.get("total_rules") is not None:
            total = int(raw.get("total_rules"))
        if enforced is None and raw.get("enforced") is not None:
            enforced = int(raw.get("enforced"))
        if rate is None:
            rate = _as_float(raw.get("enforcement_rate"))

    # 3) compute from lists if present
    if isinstance(raw, dict):
        enforced_list = (
            raw.get("enforced_rules")
            or raw.get("enforced_rule_ids")
            or raw.get("enforced")
        )
        declared_only_list = raw.get("declared_only") or raw.get("declared_only_rules")
        rules_list = raw.get("rules")

        if enforced is None and isinstance(enforced_list, list):
            enforced = len(enforced_list)

        if total is None:
            if isinstance(rules_list, list):
                total = len([x for x in rules_list if isinstance(x, (dict, str))])
            elif isinstance(enforced_list, list) and isinstance(
                declared_only_list, list
            ):
                total = len(enforced_list) + len(declared_only_list)

    # 4) derive rate if needed
    if rate is None and enforced is not None and total is not None and total > 0:
        rate = (enforced / total) * 100.0

    if enforced is None or total is None or rate is None:
        return None

    return _CoverageSnapshot(
        enforced=int(enforced),
        total=int(total),
        enforcement_rate=float(rate),
        raw=raw if isinstance(raw, dict) else {"value": raw},
        source_path=_rel(repo_path, p),
    )


# ID: 1f4e7d2c-9bd4-4a8e-9f1c-0f01d2ef4b3d
class IntegrationCoverageMinimumEnforcement(EnforcementMethod):
    """
    Enforces that governance enforcement coverage meets a declared minimum.

    This check asserts:
    - a coverage map artifact exists
    - it can be parsed into (enforced, total, enforcement_rate)
    - enforcement_rate >= declared threshold
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: 2f2c0e6a-8d0b-4a83-9c51-4d5c2fd4c1b3
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs: Any
    ) -> list[AuditFinding]:
        repo_path = context.repo_path

        threshold = _extract_threshold(rule_data)

        # If rule_data did not carry a threshold, attempt to read it from operations policy
        if threshold is None:
            try:
                operations_policy = settings.paths.policy("operations")
            except Exception:
                operations_policy = (
                    repo_path
                    / ".intent"
                    / "policies"
                    / "operations"
                    / "operations.yaml"
                )

            if operations_policy.exists():
                try:
                    doc = _safe_load(operations_policy)
                    if isinstance(doc, dict) and isinstance(doc.get("rules"), list):
                        r = next(
                            (
                                x
                                for x in doc["rules"]
                                if isinstance(x, dict)
                                and x.get("id") == RULE_INTEGRATION_COVERAGE_MINIMUM
                            ),
                            None,
                        )
                        if isinstance(r, dict):
                            threshold = _extract_threshold(r) or threshold
                except Exception as exc:
                    logger.debug(
                        "IntegrationCoverageMinimum: failed reading operations policy for threshold: %s",
                        exc,
                    )

        if threshold is None:
            return [
                _create_finding_safe(
                    self,
                    message=(
                        "integration.coverage_minimum is declared but no threshold was found "
                        "(expected e.g. minimum_enforcement_rate: 75)."
                    ),
                    file_path=str(
                        getattr(settings, "REPO_PATH", repo_path) / ".intent"
                    ),
                    severity=AuditSeverity.ERROR,
                    evidence={"rule_data": rule_data},
                )
            ]

        # Discover coverage map artifacts
        maps = _discover_coverage_map_files(repo_path)
        if not maps:
            return [
                _create_finding_safe(
                    self,
                    message=(
                        "No governance coverage map artefact discovered. "
                        "Cannot validate integration.coverage_minimum without an evidence artefact."
                    ),
                    file_path=".intent",
                    severity=AuditSeverity.ERROR,
                    evidence={
                        "threshold_percent": threshold,
                        "discovery_roots": [
                            ".intent",
                            "artifacts",
                            "reports",
                            ".cache",
                            ".tmp",
                        ],
                        "hint": "Run the governance coverage generation step to produce the coverage map artefact.",
                    },
                )
            ]

        # Parse newest-first until we get a usable snapshot
        snapshot: _CoverageSnapshot | None = None
        attempted: list[str] = []
        for p in maps[:25]:
            attempted.append(_rel(repo_path, p))
            snap = _parse_coverage_snapshot(repo_path, p)
            if snap is not None:
                snapshot = snap
                break

        if snapshot is None:
            return [
                _create_finding_safe(
                    self,
                    message="Governance coverage map artefact(s) found but none could be parsed into coverage stats.",
                    file_path=attempted[0] if attempted else ".intent",
                    severity=AuditSeverity.ERROR,
                    evidence={
                        "threshold_percent": threshold,
                        "attempted_files": attempted,
                    },
                )
            ]

        evidence = {
            "threshold_percent": threshold,
            "coverage": {
                "enforced": snapshot.enforced,
                "total": snapshot.total,
                "enforcement_rate_percent": round(snapshot.enforcement_rate, 2),
                "source": snapshot.source_path,
            },
        }

        if snapshot.total <= 0:
            return [
                _create_finding_safe(
                    self,
                    message="Coverage map reports zero total rules; cannot validate coverage minimum.",
                    file_path=snapshot.source_path,
                    severity=AuditSeverity.ERROR,
                    evidence=evidence,
                )
            ]

        if snapshot.enforcement_rate + 1e-9 < threshold:
            return [
                _create_finding_safe(
                    self,
                    message=(
                        "Governance enforcement coverage is below the declared minimum threshold "
                        "required for integration readiness."
                    ),
                    file_path=snapshot.source_path,
                    severity=AuditSeverity.ERROR,
                    evidence=evidence,
                )
            ]

        return []


# ID: 6f0c7b12-9c7b-4c76-8d2a-3f0f6a2b19c7
class IntegrationCoverageMinimumCheck(RuleEnforcementCheck):
    """
    Enforces integration.coverage_minimum.

    Ref:
    - standard_operations_general
    """

    policy_rule_ids: ClassVar[list[str]] = [RULE_INTEGRATION_COVERAGE_MINIMUM]

    # Most integration rules sit in the operations policy layer.
    policy_file: ClassVar[Path] = settings.paths.policy("operations")

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        IntegrationCoverageMinimumEnforcement(
            rule_id=RULE_INTEGRATION_COVERAGE_MINIMUM,
            severity=AuditSeverity.ERROR,
        )
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
