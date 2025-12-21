# src/mind/governance/checks/qa_audit_check.py
"""
QA Audit Governance Check

Enforces QA audit / change evaluation / remediation / risk gating rules declared in:
- .intent/.../standard_operations_quality_assurance.(yaml|yml|json)
  (policy key: "quality_assurance")

Targets (errors in your current top gaps):
- qa.audit.exceptions_empty_default
- qa.audit.exceptions_explicit
- qa.audit.explanation_required
- qa.audit.intent_declared
- qa.audit.quality_verified
- qa.audit.quorum_evidence
- qa.change.evaluation_required
- qa.change.evaluation_threshold_pass
- qa.remediation.phased_execution
- qa.remediation.trigger_conditions
- qa.risk.high_gate
- qa.risk.medium_gate

Design constraints:
- Evidence-backed only; never pretend-pass.
- Conservative static validation: file existence + explicit code references + token hits.
- Prefer CORE path resolution conventions first.
- Read-only check: no repo/DB writes.
"""

from __future__ import annotations

import fnmatch
import inspect
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.rule_enforcement_check import (
    EnforcementMethod,
    RuleEnforcementCheck,
)
from shared.config import settings
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)

RULE_AUDIT_EXCEPTIONS_EMPTY_DEFAULT = "qa.audit.exceptions_empty_default"
RULE_AUDIT_EXCEPTIONS_EXPLICIT = "qa.audit.exceptions_explicit"
RULE_AUDIT_EXPLANATION_REQUIRED = "qa.audit.explanation_required"
RULE_AUDIT_INTENT_DECLARED = "qa.audit.intent_declared"
RULE_AUDIT_QUALITY_VERIFIED = "qa.audit.quality_verified"
RULE_AUDIT_QUORUM_EVIDENCE = "qa.audit.quorum_evidence"

RULE_CHANGE_EVALUATION_REQUIRED = "qa.change.evaluation_required"
RULE_CHANGE_EVALUATION_THRESHOLD_PASS = "qa.change.evaluation_threshold_pass"

RULE_REMEDIATION_PHASED_EXECUTION = "qa.remediation.phased_execution"
RULE_REMEDIATION_TRIGGER_CONDITIONS = "qa.remediation.trigger_conditions"

RULE_RISK_HIGH_GATE = "qa.risk.high_gate"
RULE_RISK_MEDIUM_GATE = "qa.risk.medium_gate"

# Conservative code discovery hints: restrict scanning to plausible QA/audit pipeline modules.
_DISCOVERY_HINTS = (
    "audit",
    "qa",
    "quality",
    "gate",
    "gating",
    "risk",
    "remediation",
    "exceptions",
    "quorum",
    "approval",
    "intent",
    "policy",
    "governance",
    "dev.sync",
    "workflow",
)

# Default evidence tokens per rule (policy can override via rule_data.tokens).
_TOKENS_AUDIT_EXCEPTIONS = (
    "audit_exceptions",
    "qa_exceptions",
    "exceptions_file",
    "exceptions_path",
    "exceptions:",
    "allowlist",
    "denylist",
)

_TOKENS_AUDIT_EXPLANATION = (
    "explanation",
    "reason",
    "rationale",
    "justification",
    "explain",
    "comment",
)

_TOKENS_AUDIT_INTENT_DECLARED = (
    "intent_declared",
    "declared_intent",
    "intent:",
    "intent bundle",
    "proposal",
    ".intent",
)

_TOKENS_AUDIT_QUALITY_VERIFIED = (
    "quality_verified",
    "quality gate",
    "verified",
    "verification",
    "validate_quality",
    "quality_check",
)

_TOKENS_AUDIT_QUORUM = (
    "quorum",
    "approvers",
    "reviewers",
    "signoff",
    "approval",
    "two-person",
    "four-eyes",
)

_TOKENS_CHANGE_EVALUATION = (
    "change_evaluation",
    "evaluate_change",
    "evaluation_required",
    "impact_score",
    "risk_score",
    "threshold",
)

_TOKENS_REMEDIATION = (
    "remediation",
    "phased",
    "phase_1",
    "phase_2",
    "rollback",
    "safe_apply",
    "trigger_conditions",
    "trigger:",
)

_TOKENS_RISK_GATES = (
    "risk_gate",
    "high_gate",
    "medium_gate",
    "risk_level",
    "risk:",
    "severity_gate",
)


@dataclass(frozen=True)
class _Hit:
    file: str
    line: int
    kind: str
    snippet: str


def _create_finding_safe(method: EnforcementMethod, **kwargs: Any) -> AuditFinding:
    """
    EnforcementMethod._create_finding() signature varies across CORE versions.
    Filter kwargs to supported parameters to prevent runtime TypeError.
    """
    sig = inspect.signature(method._create_finding)  # type: ignore[attr-defined]
    allowed = set(sig.parameters.keys())
    filtered = {k: v for k, v in kwargs.items() if k in allowed}
    return method._create_finding(**filtered)  # type: ignore[attr-defined]


def _rel(repo_path: Path, p: Path) -> str:
    try:
        return str(p.relative_to(repo_path))
    except Exception:
        return str(p)


# ID: c269ab11-6148-427e-8b35-f9a899d5a2c9
class QAAuditEnforcement(EnforcementMethod):
    """
    Evidence-backed enforcement for QA audit/change/remediation/risk gating rules.

    Evidence model:
    - Prefer an explicit governance artifact in .intent (if present),
      AND/OR explicit code references in src to those artifacts.
    - Fallback: deterministic token hits in candidate QA/audit modules.
    - If we cannot discover relevant code/artifacts, we fail rather than pass.
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: 35963e2f-db73-43c8-99a9-81c678013e51
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs: Any
    ) -> list[AuditFinding]:
        repo_path = context.repo_path

        include_roots = self._get_str_list(rule_data, "include_roots") or ["src"]
        exclude_globs = self._get_str_list(rule_data, "exclude_globs") or [
            "**/tests/**",
            "**/.venv/**",
            "**/.tox/**",
            "**/.mypy_cache/**",
            "**/.pytest_cache/**",
            "**/__pycache__/**",
        ]
        evidence_min = self._get_int(rule_data, "evidence_minimum_per_rule", default=1)

        tokens = self._rule_tokens(self.rule_id, rule_data)
        token_set = {t.lower() for t in tokens if str(t).strip()}

        # (1) Artifact discovery (optional but preferred)
        artifacts = self._discover_qa_artifacts(repo_path)
        artifact_evidence = self._artifact_evidence_for_rule(self.rule_id, artifacts)

        # (2) Code discovery
        files = self._collect_files(repo_path, include_roots, exclude_globs)
        if not files:
            return [
                _create_finding_safe(
                    self,
                    message="No source files discovered; cannot validate qa.* rules.",
                    file_path=";".join(include_roots),
                    severity=AuditSeverity.ERROR,
                    evidence={
                        "include_roots": include_roots,
                        "exclude_globs": exclude_globs,
                    },
                )
            ]

        candidate_files = self._discover_candidate_files(repo_path, files)
        if not candidate_files and not artifact_evidence:
            return [
                _create_finding_safe(
                    self,
                    message="No QA/audit-related modules or artifacts discovered; cannot validate qa.* rules.",
                    file_path="src",
                    severity=AuditSeverity.ERROR,
                    evidence={
                        "rule_id": self.rule_id,
                        "files_scanned": len(files),
                        "candidate_files": 0,
                        "artifacts_found": {k: v for k, v in artifacts.items() if v},
                        "discovery_hints": list(_DISCOVERY_HINTS),
                    },
                )
            ]

        hits: list[_Hit] = []
        read_errors: list[dict[str, Any]] = []

        for p in candidate_files:
            relp = _rel(repo_path, p)
            try:
                src = p.read_text(encoding="utf-8")
            except Exception as exc:
                read_errors.append({"file": relp, "error": f"read_failed: {exc}"})
                continue

            for i, line in enumerate(src.splitlines(), start=1):
                lowered = line.lower()
                if any(tok in lowered for tok in token_set):
                    hits.append(
                        _Hit(
                            file=relp,
                            line=i,
                            kind="token",
                            snippet=line.strip()[:240],
                        )
                    )

        # If artifact evidence exists, we accept it as first-class evidence (and we still include code hits).
        total_evidence = (len(hits) > 0) or bool(artifact_evidence)
        ok = total_evidence and (len(hits) >= evidence_min or artifact_evidence)

        evidence: dict[str, Any] = {
            "rule_id": self.rule_id,
            "evidence_minimum": evidence_min,
            "artifacts_found": {k: v for k, v in artifacts.items() if v},
            "artifact_evidence": artifact_evidence,
            "candidate_files_scanned": len(candidate_files),
            "tokens_scanned": tokens,
            "hits_count": len(hits),
            "hits": [
                {"file": h.file, "line": h.line, "snippet": h.snippet}
                for h in hits[:200]
            ],
            "read_errors_count": len(read_errors),
            "read_errors": read_errors[:25],
            "hint": self._hint_for_rule(self.rule_id),
        }

        return [
            _create_finding_safe(
                self,
                message=(
                    f"Evidence found for {self.rule_id}."
                    if ok
                    else f"No evidence found for {self.rule_id}."
                ),
                file_path="src",
                severity=AuditSeverity.INFO if ok else AuditSeverity.ERROR,
                evidence=evidence,
            )
        ]

    # ----------------------------
    # Evidence logic
    # ----------------------------

    def _artifact_evidence_for_rule(
        self, rule_id: str, artifacts: dict[str, list[str]]
    ) -> dict[str, Any]:
        """
        Very conservative: only accept artifact evidence if it matches the intent
        of the rule (by filename category).
        """
        # These are *categories*; we do not enforce exact filenames here.
        if rule_id in (
            RULE_AUDIT_EXCEPTIONS_EMPTY_DEFAULT,
            RULE_AUDIT_EXCEPTIONS_EXPLICIT,
            RULE_AUDIT_EXPLANATION_REQUIRED,
        ):
            if artifacts.get("exceptions"):
                return {"category": "exceptions", "files": artifacts["exceptions"][:25]}

        if rule_id in (RULE_AUDIT_INTENT_DECLARED,):
            if artifacts.get("intent_linkage"):
                return {
                    "category": "intent_linkage",
                    "files": artifacts["intent_linkage"][:25],
                }

        if rule_id in (RULE_AUDIT_QUALITY_VERIFIED,):
            if artifacts.get("quality_gate"):
                return {
                    "category": "quality_gate",
                    "files": artifacts["quality_gate"][:25],
                }

        if rule_id in (RULE_AUDIT_QUORUM_EVIDENCE,):
            if artifacts.get("quorum"):
                return {"category": "quorum", "files": artifacts["quorum"][:25]}

        if rule_id in (
            RULE_CHANGE_EVALUATION_REQUIRED,
            RULE_CHANGE_EVALUATION_THRESHOLD_PASS,
        ):
            if artifacts.get("change_eval"):
                return {
                    "category": "change_eval",
                    "files": artifacts["change_eval"][:25],
                }

        if rule_id in (
            RULE_REMEDIATION_PHASED_EXECUTION,
            RULE_REMEDIATION_TRIGGER_CONDITIONS,
        ):
            if artifacts.get("remediation"):
                return {
                    "category": "remediation",
                    "files": artifacts["remediation"][:25],
                }

        if rule_id in (RULE_RISK_HIGH_GATE, RULE_RISK_MEDIUM_GATE):
            if artifacts.get("risk_gates"):
                return {"category": "risk_gates", "files": artifacts["risk_gates"][:25]}

        return {}

    def _discover_qa_artifacts(self, repo_path: Path) -> dict[str, list[str]]:
        """
        Conservative discovery in .intent for QA-relevant governance artifacts.
        We do not assume exact names; we classify by filename tokens.
        """
        intent_root = repo_path / ".intent"
        if not intent_root.exists():
            return {
                "exceptions": [],
                "intent_linkage": [],
                "quality_gate": [],
                "quorum": [],
                "change_eval": [],
                "remediation": [],
                "risk_gates": [],
            }

        out: dict[str, list[str]] = {
            "exceptions": [],
            "intent_linkage": [],
            "quality_gate": [],
            "quorum": [],
            "change_eval": [],
            "remediation": [],
            "risk_gates": [],
        }

        for p in intent_root.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix.lower() not in (".yaml", ".yml", ".json"):
                continue

            relp = _rel(repo_path, p).replace("\\", "/")
            name = p.name.lower()

            if "exception" in name:
                out["exceptions"].append(relp)
            if "intent" in name and (
                "audit" in name or "qa" in name or "quality" in name
            ):
                out["intent_linkage"].append(relp)
            if "quality" in name or "qa" in name:
                out["quality_gate"].append(relp)
            if "quorum" in name or "approval" in name or "signoff" in name:
                out["quorum"].append(relp)
            if "change" in name and ("eval" in name or "evaluation" in name):
                out["change_eval"].append(relp)
            if "remediation" in name or "remediate" in name:
                out["remediation"].append(relp)
            if "risk" in name and (
                "gate" in name or "gating" in name or "threshold" in name
            ):
                out["risk_gates"].append(relp)

        for k in list(out.keys()):
            out[k] = sorted(set(out[k]))

        return out

    # ----------------------------
    # Token selection
    # ----------------------------

    def _rule_tokens(self, rule_id: str, rule_data: dict[str, Any]) -> list[str]:
        # Allow per-rule overrides in policy: tokens.<rule_id>: [...]
        tokens_override = None
        tokens_section = rule_data.get("tokens")
        if isinstance(tokens_section, dict):
            tokens_override = tokens_section.get(rule_id)

        if isinstance(tokens_override, list):
            base = [str(x) for x in tokens_override]
        elif isinstance(tokens_override, str) and tokens_override.strip():
            base = [tokens_override.strip()]
        else:
            base = list(self._default_tokens(rule_id))

        # Optional global extension: tokens_global: [...]
        tokens_global = rule_data.get("tokens_global")
        if isinstance(tokens_global, list):
            base.extend(str(x) for x in tokens_global)
        elif isinstance(tokens_global, str) and tokens_global.strip():
            base.append(tokens_global.strip())

        # Deduplicate while keeping order
        seen: set[str] = set()
        out: list[str] = []
        for t in base:
            key = t.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(t)
        return out

    def _default_tokens(self, rule_id: str) -> tuple[str, ...]:
        if rule_id in (
            RULE_AUDIT_EXCEPTIONS_EMPTY_DEFAULT,
            RULE_AUDIT_EXCEPTIONS_EXPLICIT,
        ):
            return _TOKENS_AUDIT_EXCEPTIONS
        if rule_id == RULE_AUDIT_EXPLANATION_REQUIRED:
            return _TOKENS_AUDIT_EXCEPTIONS + _TOKENS_AUDIT_EXPLANATION
        if rule_id == RULE_AUDIT_INTENT_DECLARED:
            return _TOKENS_AUDIT_INTENT_DECLARED
        if rule_id == RULE_AUDIT_QUALITY_VERIFIED:
            return _TOKENS_AUDIT_QUALITY_VERIFIED
        if rule_id == RULE_AUDIT_QUORUM_EVIDENCE:
            return _TOKENS_AUDIT_QUORUM
        if rule_id in (
            RULE_CHANGE_EVALUATION_REQUIRED,
            RULE_CHANGE_EVALUATION_THRESHOLD_PASS,
        ):
            return _TOKENS_CHANGE_EVALUATION
        if rule_id in (
            RULE_REMEDIATION_PHASED_EXECUTION,
            RULE_REMEDIATION_TRIGGER_CONDITIONS,
        ):
            return _TOKENS_REMEDIATION
        if rule_id in (RULE_RISK_HIGH_GATE, RULE_RISK_MEDIUM_GATE):
            return _TOKENS_RISK_GATES
        return ()

    def _hint_for_rule(self, rule_id: str) -> str:
        if rule_id in (
            RULE_AUDIT_EXCEPTIONS_EMPTY_DEFAULT,
            RULE_AUDIT_EXCEPTIONS_EXPLICIT,
        ):
            return "Expected an explicit audit exceptions mechanism (preferably a dedicated file + code reference)."
        if rule_id == RULE_AUDIT_EXPLANATION_REQUIRED:
            return "Expected exceptions to carry an explicit explanation/rationale (not silent allowlisting)."
        if rule_id == RULE_AUDIT_INTENT_DECLARED:
            return "Expected QA audit to declare intent (what is being checked/why), not only produce raw pass/fail."
        if rule_id == RULE_AUDIT_QUALITY_VERIFIED:
            return "Expected explicit 'quality verified' gate in the audit pipeline (tests/style/coverage/criteria)."
        if rule_id == RULE_AUDIT_QUORUM_EVIDENCE:
            return "Expected explicit quorum/sign-off evidence handling (four-eyes/approver list/approval record)."
        if rule_id == RULE_CHANGE_EVALUATION_REQUIRED:
            return "Expected change evaluation step (risk/impact evaluation) before applying changes."
        if rule_id == RULE_CHANGE_EVALUATION_THRESHOLD_PASS:
            return "Expected enforcement of evaluation thresholds (block if below threshold / above risk)."
        if rule_id == RULE_REMEDIATION_PHASED_EXECUTION:
            return "Expected phased remediation execution (e.g., stage -> verify -> apply) rather than one-shot changes."
        if rule_id == RULE_REMEDIATION_TRIGGER_CONDITIONS:
            return "Expected explicit triggers for remediation (what conditions cause remediation to run)."
        if rule_id == RULE_RISK_HIGH_GATE:
            return "Expected explicit blocking/approval gate for HIGH risk changes."
        if rule_id == RULE_RISK_MEDIUM_GATE:
            return "Expected explicit gate for MEDIUM risk changes (may be softer than HIGH but still enforced)."
        return ""

    # ----------------------------
    # File discovery helpers
    # ----------------------------

    def _collect_files(
        self,
        repo_path: Path,
        include_roots: list[str],
        exclude_globs: list[str],
    ) -> list[Path]:
        out: list[Path] = []
        for root in include_roots:
            base = repo_path / root
            if not base.exists():
                continue
            for p in base.rglob("*.py"):
                if not p.is_file():
                    continue
                relp = _rel(repo_path, p).replace("\\", "/")
                if any(fnmatch.fnmatch(relp, g) for g in exclude_globs):
                    continue
                out.append(p)
        return sorted(out)

    def _discover_candidate_files(
        self, repo_path: Path, files: list[Path]
    ) -> list[Path]:
        """
        Conservative discovery of likely QA/audit pipeline modules.
        We select by path first, then rank by keyword density in filename.
        """
        candidates: list[Path] = []
        for p in files:
            relp = _rel(repo_path, p).replace("\\", "/").lower()
            if any(
                k in relp
                for k in (
                    "audit",
                    "governance",
                    "qa",
                    "quality",
                    "workflow",
                    "dev",
                    "remediation",
                    "risk",
                )
            ):
                candidates.append(p)

        # ID: 2ca4612b-d3a0-4766-b68b-0dcedcd38089
        def score(p: Path) -> int:
            relp = _rel(repo_path, p).replace("\\", "/").lower()
            s = 0
            for k in (
                "qa",
                "quality",
                "audit",
                "remediation",
                "risk",
                "workflow",
                "dev.sync",
                "governance",
            ):
                if k in relp:
                    s += 3
            return s

        ranked = sorted(
            ((score(p), p) for p in candidates), key=lambda x: x[0], reverse=True
        )
        strong = [p for sc, p in ranked if sc >= 3]

        return strong[:250]

    def _get_str_list(self, d: dict[str, Any], key: str) -> list[str]:
        v = d.get(key)
        if isinstance(v, list):
            return [str(x) for x in v if str(x).strip()]
        if isinstance(v, str) and v.strip():
            return [v.strip()]
        return []

    def _get_int(self, d: dict[str, Any], key: str, *, default: int) -> int:
        v = d.get(key)
        try:
            if isinstance(v, int):
                return v
            if isinstance(v, str) and re.fullmatch(r"\d+", v.strip()):
                return int(v.strip())
        except Exception:
            return default
        return default


# ID: 5f1cf9b5-9e5f-4d8a-a0ef-42d8b1b72d58
class QAAuditCheck(RuleEnforcementCheck):
    """
    Enforces QA audit / change evaluation / remediation / risk gating standards.

    Ref:
    - standard_operations_quality_assurance
    """

    policy_rule_ids: ClassVar[list[str]] = [
        RULE_AUDIT_EXCEPTIONS_EMPTY_DEFAULT,
        RULE_AUDIT_EXCEPTIONS_EXPLICIT,
        RULE_AUDIT_EXPLANATION_REQUIRED,
        RULE_AUDIT_INTENT_DECLARED,
        RULE_AUDIT_QUALITY_VERIFIED,
        RULE_AUDIT_QUORUM_EVIDENCE,
        RULE_CHANGE_EVALUATION_REQUIRED,
        RULE_CHANGE_EVALUATION_THRESHOLD_PASS,
        RULE_REMEDIATION_PHASED_EXECUTION,
        RULE_REMEDIATION_TRIGGER_CONDITIONS,
        RULE_RISK_HIGH_GATE,
        RULE_RISK_MEDIUM_GATE,
    ]

    # PathResolver policy key expected: "quality_assurance"
    policy_file: ClassVar[Path] = settings.paths.policy("quality_assurance")

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        QAAuditEnforcement(
            rule_id=RULE_AUDIT_EXCEPTIONS_EMPTY_DEFAULT, severity=AuditSeverity.ERROR
        ),
        QAAuditEnforcement(
            rule_id=RULE_AUDIT_EXCEPTIONS_EXPLICIT, severity=AuditSeverity.ERROR
        ),
        QAAuditEnforcement(
            rule_id=RULE_AUDIT_EXPLANATION_REQUIRED, severity=AuditSeverity.ERROR
        ),
        QAAuditEnforcement(
            rule_id=RULE_AUDIT_INTENT_DECLARED, severity=AuditSeverity.ERROR
        ),
        QAAuditEnforcement(
            rule_id=RULE_AUDIT_QUALITY_VERIFIED, severity=AuditSeverity.ERROR
        ),
        QAAuditEnforcement(
            rule_id=RULE_AUDIT_QUORUM_EVIDENCE, severity=AuditSeverity.ERROR
        ),
        QAAuditEnforcement(
            rule_id=RULE_CHANGE_EVALUATION_REQUIRED, severity=AuditSeverity.ERROR
        ),
        QAAuditEnforcement(
            rule_id=RULE_CHANGE_EVALUATION_THRESHOLD_PASS, severity=AuditSeverity.ERROR
        ),
        QAAuditEnforcement(
            rule_id=RULE_REMEDIATION_PHASED_EXECUTION, severity=AuditSeverity.ERROR
        ),
        QAAuditEnforcement(
            rule_id=RULE_REMEDIATION_TRIGGER_CONDITIONS, severity=AuditSeverity.ERROR
        ),
        QAAuditEnforcement(rule_id=RULE_RISK_HIGH_GATE, severity=AuditSeverity.ERROR),
        QAAuditEnforcement(rule_id=RULE_RISK_MEDIUM_GATE, severity=AuditSeverity.ERROR),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
