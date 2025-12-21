# src/mind/governance/checks/integration_audit_required_check.py
"""
Integration Audit Required Governance Check

Enforces integration audit gating rules declared in:
- .intent/charter/standards/operations/operations.(yaml|yml|json)
  (policy key commonly: "operations")

Targets:
- integration.audit_required

Design constraints:
- Prefer internal CORE capabilities first (Body integration checker / CLI logic).
- Fall back to conservative static evidence checks (CI config / scripts).
- Evidence-backed; do not pretend-pass when evidence cannot be established.
- Compatible with varying EnforcementMethod._create_finding() signatures.
"""

from __future__ import annotations

import inspect
import json
import re
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

RULE_INTEGRATION_AUDIT_REQUIRED = "integration.audit_required"


def _safe_load(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text)
    return yaml.safe_load(text)


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


def _extract_rules(policy_doc: Any) -> list[dict[str, Any]]:
    if not isinstance(policy_doc, dict):
        return []
    rules = policy_doc.get("rules")
    if not isinstance(rules, list):
        return []
    return [r for r in rules if isinstance(r, dict)]


def _rel(repo_path: Path, p: Path) -> str:
    try:
        return str(p.relative_to(repo_path))
    except Exception:
        return str(p)


def _read_text_best_effort(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _discover_ci_files(repo_path: Path) -> list[Path]:
    """
    Conservative discovery for common CI entrypoints.
    """
    candidates: list[Path] = []

    gha = repo_path / ".github" / "workflows"
    if gha.exists():
        candidates.extend(sorted(p for p in gha.rglob("*") if p.is_file()))

    gl = repo_path / ".gitlab-ci.yml"
    if gl.exists():
        candidates.append(gl)

    jf = repo_path / "Jenkinsfile"
    if jf.exists():
        candidates.append(jf)

    scripts = repo_path / "scripts"
    if scripts.exists():
        candidates.extend(sorted(p for p in scripts.rglob("*") if p.is_file()))

    mk = repo_path / "Makefile"
    if mk.exists():
        candidates.append(mk)

    tox = repo_path / "tox.ini"
    if tox.exists():
        candidates.append(tox)

    pyproject = repo_path / "pyproject.toml"
    if pyproject.exists():
        candidates.append(pyproject)

    # Deduplicate
    uniq = sorted({p.resolve() for p in candidates})
    return [Path(p) for p in uniq]


def _audit_evidence_lines(text: str) -> list[str]:
    """
    Extract evidence lines indicating governance audit runs as part of integration.

    We treat "audit required" as: a pipeline path that explicitly runs the CORE audit
    (or equivalent governance validation), not only tests.
    """
    patterns = [
        # CORE-native governance commands
        r"\bcore-admin\b.*\bgovernance\b.*\baudit\b",
        r"\bcore-admin\b.*\baudit\b",
        r"\bgovernance\b.*\baudit\b",
        # Direct Python invocations (rare, but acceptable)
        r"\bpython\b.*\bcore-admin\b.*\baudit\b",
        # Generic "audit" tasks (we keep conservative by requiring governance/intent hints)
        r"\bmake\b.*\baudit\b",
        r"\btox\b.*\baudit\b",
        # Intent/schema validation often paired with audit in CORE
        r"\bintent\b.*\b(validate|schema|check)\b",
        r"\bvalidate\b.*\b\.intent\b",
    ]

    hits: list[str] = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        ln = line.strip()
        if not ln or ln.startswith("#"):
            continue
        for pat in patterns:
            if re.search(pat, ln, flags=re.IGNORECASE):
                hits.append(f"line {i + 1}: {ln[:240]}")
                break
        if len(hits) >= 20:
            break
    return hits


def _try_run_internal_integration_checker(repo_path: Path) -> dict[str, Any] | None:
    """
    Preferred: reuse CORE-native integration/dev-fastpath checking logic if present.
    """
    mod = None
    for candidate in ("integration_checker", "dev_fastpath_checker"):
        try:
            from body.cli.logic import (  # type: ignore
                __dict__ as _unused,  # noqa: F401
            )
        except Exception:
            # guard import system oddities
            pass

        try:
            mod = __import__("body.cli.logic." + candidate, fromlist=[candidate])
            break
        except Exception:
            mod = None

    if mod is None:
        return None

    entrypoints = ("check", "run", "run_check", "analyze", "scan", "validate")
    fn = None
    for name in entrypoints:
        cand = getattr(mod, name, None)
        if callable(cand):
            fn = cand
            break
    if fn is None:
        return None

    try:
        out = fn(repo_path)
    except TypeError:
        try:
            out = fn()
        except Exception:
            return None
    except Exception:
        return None

    if isinstance(out, dict):
        return out
    if hasattr(out, "to_dict") and callable(getattr(out, "to_dict")):
        try:
            d = out.to_dict()
            if isinstance(d, dict):
                return d
        except Exception:
            return None

    return None


# ID: 6f6c9dbb-1d5c-4d72-9db7-3e6a33e7d702
class IntegrationAuditRequiredEnforcement(EnforcementMethod):
    """
    Evidence-backed check for integration.audit_required.

    We validate (conservative):
    1) The rule exists in the operations policy.
    2) There is credible gating evidence that a governance audit is executed as part of integration:
       - Preferred: internal CORE integration checker returns positive evidence.
       - Fallback: CI/workflow files contain explicit governance audit execution steps.
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: 7a7d54c2-09e1-4ad8-a7ce-0f7d4c0e57d7
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs: Any
    ) -> list[AuditFinding]:
        repo_path = context.repo_path

        # Policy resolution (canonical first)
        try:
            policy_path = settings.paths.policy("operations")
        except Exception:
            policy_path = (
                repo_path
                / ".intent"
                / "charter"
                / "standards"
                / "operations"
                / "operations.yaml"
            )

        if not isinstance(policy_path, Path):
            policy_path = Path(policy_path)

        if not policy_path.exists():
            return [
                _create_finding_safe(
                    self,
                    message="Operations policy file missing; cannot validate integration.audit_required.",
                    file_path=_rel(repo_path, policy_path),
                    severity=AuditSeverity.ERROR,
                )
            ]

        try:
            policy_doc = _safe_load(policy_path)
        except Exception as exc:
            return [
                _create_finding_safe(
                    self,
                    message=f"Failed to parse operations policy: {exc}",
                    file_path=_rel(repo_path, policy_path),
                    severity=AuditSeverity.ERROR,
                )
            ]

        rules = _extract_rules(policy_doc)
        this_rule = next(
            (r for r in rules if r.get("id") == RULE_INTEGRATION_AUDIT_REQUIRED), None
        )
        if not this_rule:
            return [
                _create_finding_safe(
                    self,
                    message="integration.audit_required rule not declared in operations policy.",
                    file_path=_rel(repo_path, policy_path),
                    severity=AuditSeverity.ERROR,
                )
            ]

        # Preferred: internal checker evidence
        internal = _try_run_internal_integration_checker(repo_path)
        if internal is not None:
            passed = bool(
                internal.get("audit_required")
                or internal.get(RULE_INTEGRATION_AUDIT_REQUIRED)
                or internal.get("ok_audit")
            )
            if passed:
                return []

            return [
                _create_finding_safe(
                    self,
                    message="Internal integration checker did not confirm that governance audit is executed as part of integration.",
                    file_path=_rel(repo_path, policy_path),
                    severity=AuditSeverity.ERROR,
                    evidence={
                        "source": "internal_checker",
                        "checker_output": internal,
                        "policy_rule": this_rule,
                    },
                )
            ]

        # Fallback: CI/workflow evidence
        ci_files = _discover_ci_files(repo_path)
        if not ci_files:
            return [
                _create_finding_safe(
                    self,
                    message=(
                        "No CI/workflow files discovered; cannot establish evidence that integration enforces "
                        "a governance audit run."
                    ),
                    file_path=_rel(repo_path, repo_path),
                    severity=AuditSeverity.ERROR,
                    evidence={
                        "source": "ci_discovery",
                        "searched": [
                            ".github/workflows/**",
                            ".gitlab-ci.yml",
                            "Jenkinsfile",
                            "scripts/**",
                            "Makefile",
                            "tox.ini",
                            "pyproject.toml",
                        ],
                        "policy_rule": this_rule,
                    },
                )
            ]

        hits: list[dict[str, Any]] = []
        for p in ci_files:
            txt = _read_text_best_effort(p)
            if not txt:
                continue
            evidence_lines = _audit_evidence_lines(txt)
            if evidence_lines:
                hits.append({"file": _rel(repo_path, p), "evidence": evidence_lines})
            if len(hits) >= 5:
                break

        if not hits:
            return [
                _create_finding_safe(
                    self,
                    message=(
                        "CI/workflow files were found, but no clear evidence of a governance audit execution "
                        "step was detected (e.g., 'core-admin governance audit')."
                    ),
                    file_path=_rel(repo_path, policy_path),
                    severity=AuditSeverity.ERROR,
                    evidence={
                        "source": "ci_scan",
                        "scanned_files": [_rel(repo_path, p) for p in ci_files[:25]],
                        "policy_rule": this_rule,
                    },
                )
            ]

        # Evidence exists -> pass
        return []


# ID: 4d74abfe-9f6f-4b47-9d2c-50bce7db02d2
class IntegrationAuditRequiredCheck(RuleEnforcementCheck):
    """
    Enforces integration.audit_required via evidence-backed validation.
    """

    policy_rule_ids: ClassVar[list[str]] = [RULE_INTEGRATION_AUDIT_REQUIRED]

    policy_file: ClassVar[Path] = settings.paths.policy("operations")

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        IntegrationAuditRequiredEnforcement(
            rule_id=RULE_INTEGRATION_AUDIT_REQUIRED,
            severity=AuditSeverity.ERROR,
        )
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
