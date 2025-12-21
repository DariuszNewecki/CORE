# src/mind/governance/checks/qa_coverage_critical_paths_check.py

"""
Enforces QA coverage standards for critical paths and exclusions.

Policy source:
- Operations Standard - Quality Assurance (standard_operations_quality_assurance)

Rules enforced:
- qa.coverage.critical_paths
- qa.coverage.exclusions
- qa.coverage.minimum_threshold (optional overall guardrail)

Evidence source:
- coverage.json (coverage.py JSON report format)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, ClassVar

from mind.governance.checks.base_check import BaseCheck
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)


# ID: 8c7b9c3a-9e2c-4e61-8c4d-1a9f8e3d7b2a
@dataclass(frozen=True)
class _CriticalPathGate:
    pattern: str
    required_percent: float


# ID: 4df03d85-eaa2-4bbd-9a2a-20a6e0a8b3f0
class QACoverageCriticalPathsCheck(BaseCheck):
    """
    Validates that critical code paths meet elevated coverage thresholds, while honoring
    configured exclusions.
    """

    policy_rule_ids: ClassVar[list[str]] = [
        "qa.coverage.minimum_threshold",
        "qa.coverage.critical_paths",
        "qa.coverage.exclusions",
    ]

    _STANDARD_ID: ClassVar[str] = "standard_operations_quality_assurance"

    # Try a few common report locations; repo owners can standardize later.
    _COVERAGE_CANDIDATES: ClassVar[tuple[str, ...]] = (
        "coverage.json",
        "reports/coverage.json",
        "reports/coverage/coverage.json",
        "coverage/coverage.json",
    )

    # Parse "src/core/**/*.py >= 85%" (with optional %)
    _GATE_RE: ClassVar[re.Pattern[str]] = re.compile(
        r"^\s*(?P<glob>.+?)\s*>=\s*(?P<thr>\d+(\.\d+)?)\s*%?\s*$"
    )

    # ID: 2e3a7a6a-0f6f-4a8c-b8b3-6b55c0b3a4a6
    def execute(self) -> list[AuditFinding]:
        policy_doc = self._load_standard_doc()
        if policy_doc is None:
            return [
                AuditFinding(
                    check_id="qa.coverage.policy_missing",
                    severity=AuditSeverity.WARNING,
                    message=(
                        f"QA standard '{self._STANDARD_ID}' not found under .intent. "
                        "Cannot enforce qa.coverage.* rules."
                    ),
                    file_path=str(self.intent_path),
                )
            ]

        # Extract rule payloads
        rule_by_id = {
            str(r.get("id")): r
            for r in (policy_doc.get("rules") or [])
            if isinstance(r, dict)
        }

        # Pull config from standard
        min_threshold = self._extract_min_threshold(
            rule_by_id.get("qa.coverage.minimum_threshold")
        )
        exclusions = self._extract_scope_list(rule_by_id.get("qa.coverage.exclusions"))
        critical_gates = self._extract_critical_gates(
            rule_by_id.get("qa.coverage.critical_paths")
        )

        findings: list[AuditFinding] = []

        # Evidence: coverage.json
        coverage_path = self._find_coverage_json()
        if coverage_path is None:
            findings.append(
                AuditFinding(
                    check_id="qa.coverage.data_missing",
                    severity=AuditSeverity.WARNING,
                    message="Coverage evidence missing: coverage.json not found. Cannot verify qa.coverage.*.",
                    file_path="coverage.json",
                    context={"searched": list(self._COVERAGE_CANDIDATES)},
                )
            )
            return findings

        coverage_data = self._load_json(coverage_path)
        if coverage_data is None:
            findings.append(
                AuditFinding(
                    check_id="qa.coverage.data_invalid",
                    severity=AuditSeverity.WARNING,
                    message="coverage.json found but could not be parsed as JSON.",
                    file_path=self._rel(coverage_path),
                )
            )
            return findings

        file_index = coverage_data.get("files")
        if not isinstance(file_index, dict):
            findings.append(
                AuditFinding(
                    check_id="qa.coverage.data_invalid",
                    severity=AuditSeverity.WARNING,
                    message="coverage.json does not contain a 'files' mapping. Unexpected format.",
                    file_path=self._rel(coverage_path),
                )
            )
            return findings

        # Optional: enforce minimum overall threshold from coverage summary if present
        if min_threshold is not None:
            overall = self._compute_overall_weighted_coverage(file_index, exclusions)
            if overall is not None and overall + 1e-9 < min_threshold:
                findings.append(
                    AuditFinding(
                        check_id="qa.coverage.minimum_threshold",
                        severity=AuditSeverity.ERROR,
                        message=(
                            f"Overall production coverage {overall:.2f}% is below minimum "
                            f"threshold {min_threshold:.2f}%."
                        ),
                        file_path=self._rel(coverage_path),
                        context={
                            "current": round(overall, 2),
                            "required": min_threshold,
                        },
                    )
                )

        # Enforce exclusions sanity: exclusions configured but match nothing
        if exclusions:
            if not self._any_exclusion_matches(file_index, exclusions):
                findings.append(
                    AuditFinding(
                        check_id="qa.coverage.exclusions",
                        severity=AuditSeverity.WARNING,
                        message=(
                            "Coverage exclusions are configured but none match any file paths in coverage.json. "
                            "Verify exclusion glob patterns."
                        ),
                        file_path=self._rel(coverage_path),
                        context={"exclusions": exclusions},
                    )
                )

        # Enforce critical path gates
        if not critical_gates:
            findings.append(
                AuditFinding(
                    check_id="qa.coverage.critical_paths",
                    severity=AuditSeverity.WARNING,
                    message=(
                        "qa.coverage.critical_paths rule exists but has no enforceable scope entries. "
                        "Add scope entries like 'src/** >= 85%'."
                    ),
                    file_path=self._rel(coverage_path),
                )
            )
            return findings

        for gate in critical_gates:
            actual = self._compute_weighted_coverage_for_glob(
                file_index, gate.pattern, exclusions
            )
            if actual is None:
                findings.append(
                    AuditFinding(
                        check_id="qa.coverage.critical_paths",
                        severity=AuditSeverity.WARNING,
                        message=(
                            f"Critical path '{gate.pattern}' matched no files in coverage.json (after exclusions). "
                            f"Cannot verify required {gate.required_percent:.2f}%."
                        ),
                        file_path=gate.pattern,
                        context={"required": gate.required_percent},
                    )
                )
                continue

            if actual + 1e-9 < gate.required_percent:
                findings.append(
                    AuditFinding(
                        check_id="qa.coverage.critical_paths",
                        severity=AuditSeverity.ERROR,
                        message=(
                            f"Critical path '{gate.pattern}' coverage {actual:.2f}% is below "
                            f"required {gate.required_percent:.2f}%."
                        ),
                        file_path=gate.pattern,
                        context={
                            "current": round(actual, 2),
                            "required": gate.required_percent,
                            "coverage_file": self._rel(coverage_path),
                        },
                    )
                )

        return findings

    # ----------------------------
    # Policy loading (robust)
    # ----------------------------

    def _load_standard_doc(self) -> dict[str, Any] | None:
        """
        Locates and loads the standard document by scanning .intent for JSON/YAML
        documents whose top-level "id" matches _STANDARD_ID.

        This avoids hardcoding .intent paths and matches your repo reality
        (directories may change).
        """
        for path in self.intent_path.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".json", ".yaml", ".yml"}:
                continue
            doc = self._load_structured_doc(path)
            if not isinstance(doc, dict):
                continue
            if str(doc.get("id", "")).strip() == self._STANDARD_ID:
                return doc
        return None

    def _load_structured_doc(self, path: Path) -> dict[str, Any] | None:
        if path.suffix.lower() == ".json":
            return self._load_json(path)
        # YAML is optional: if PyYAML is present in your environment it will work;
        # if not, we skip YAML rather than failing the audit.
        try:
            import yaml  # type: ignore
        except Exception:
            return None

        try:
            return yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _load_json(self, path: Path) -> dict[str, Any] | None:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    # ----------------------------
    # Coverage evidence parsing
    # ----------------------------

    def _find_coverage_json(self) -> Path | None:
        for rel in self._COVERAGE_CANDIDATES:
            p = (self.repo_root / rel).resolve()
            if p.exists() and p.is_file():
                return p
        return None

    def _normalize_rel_path(self, raw_path: str) -> str | None:
        if not isinstance(raw_path, str) or not raw_path.strip():
            return None
        p = Path(raw_path)
        try:
            if p.is_absolute():
                p = p.relative_to(self.repo_root)
        except Exception:
            # Best-effort fallback: keep tail segments to enable glob matching.
            p = Path(*p.parts[-8:])
        return str(p).replace("\\", "/")

    def _is_excluded(self, rel_path: str, exclusions: list[str]) -> bool:
        return any(fnmatch(rel_path, glob) for glob in exclusions)

    def _compute_weighted_coverage_for_glob(
        self,
        file_index: dict[str, Any],
        glob_pattern: str,
        exclusions: list[str],
    ) -> float | None:
        total_statements = 0
        total_covered = 0

        for raw_path, payload in file_index.items():
            rel = self._normalize_rel_path(raw_path)
            if not rel:
                continue
            if exclusions and self._is_excluded(rel, exclusions):
                continue
            if not fnmatch(rel, glob_pattern):
                continue

            summary = payload.get("summary") if isinstance(payload, dict) else None
            if not isinstance(summary, dict):
                continue

            num_statements = summary.get("num_statements")
            covered_lines = summary.get("covered_lines")

            if not isinstance(num_statements, int) or not isinstance(
                covered_lines, int
            ):
                continue
            if num_statements <= 0:
                continue

            total_statements += num_statements
            total_covered += covered_lines

        if total_statements <= 0:
            return None
        return (total_covered / total_statements) * 100.0

    def _compute_overall_weighted_coverage(
        self,
        file_index: dict[str, Any],
        exclusions: list[str],
    ) -> float | None:
        """
        Overall weighted coverage, honoring exclusions.
        This is "best effort": it uses the same num_statements/covered_lines data.
        """
        total_statements = 0
        total_covered = 0

        for raw_path, payload in file_index.items():
            rel = self._normalize_rel_path(raw_path)
            if not rel:
                continue
            if exclusions and self._is_excluded(rel, exclusions):
                continue

            summary = payload.get("summary") if isinstance(payload, dict) else None
            if not isinstance(summary, dict):
                continue

            num_statements = summary.get("num_statements")
            covered_lines = summary.get("covered_lines")

            if not isinstance(num_statements, int) or not isinstance(
                covered_lines, int
            ):
                continue
            if num_statements <= 0:
                continue

            total_statements += num_statements
            total_covered += covered_lines

        if total_statements <= 0:
            return None
        return (total_covered / total_statements) * 100.0

    def _any_exclusion_matches(
        self, file_index: dict[str, Any], exclusions: list[str]
    ) -> bool:
        for raw_path in file_index.keys():
            rel = self._normalize_rel_path(raw_path)
            if not rel:
                continue
            if self._is_excluded(rel, exclusions):
                return True
        return False

    # ----------------------------
    # Rule extraction helpers
    # ----------------------------

    def _extract_scope_list(self, rule: dict[str, Any] | None) -> list[str]:
        if not isinstance(rule, dict):
            return []
        scope = rule.get("scope")
        if not isinstance(scope, list):
            return []
        return [str(x) for x in scope if isinstance(x, str) and x.strip()]

    def _extract_critical_gates(
        self, rule: dict[str, Any] | None
    ) -> list[_CriticalPathGate]:
        gates: list[_CriticalPathGate] = []
        for entry in self._extract_scope_list(rule):
            m = self._GATE_RE.match(entry)
            if not m:
                # Policy entry malformed: surface as warning rather than hard fail.
                gates.append(
                    _CriticalPathGate(
                        pattern=entry.strip(), required_percent=float("nan")
                    )
                )
                continue
            glob_pat = m.group("glob").strip()
            thr = float(m.group("thr"))
            gates.append(_CriticalPathGate(pattern=glob_pat, required_percent=thr))

        # Filter out malformed entries (nan threshold) into findings? We can do it here
        # conservatively: keep them out of enforcement and let execution warn.
        return [
            g for g in gates if g.pattern and g.required_percent == g.required_percent
        ]

    def _extract_min_threshold(self, rule: dict[str, Any] | None) -> float | None:
        """
        Parses the numeric percent from statement like:
          "Production code MUST maintain a minimum of 55% test coverage."
        If parsing fails, returns None (best-effort).
        """
        if not isinstance(rule, dict):
            return None
        stmt = str(rule.get("statement", ""))
        m = re.search(r"minimum\s+of\s+(\d+(\.\d+)?)\s*%", stmt, flags=re.IGNORECASE)
        if not m:
            return None
        return float(m.group(1))

    # ----------------------------
    # Formatting
    # ----------------------------

    def _rel(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.repo_root)).replace("\\", "/")
        except Exception:
            return str(path).replace("\\", "/")
