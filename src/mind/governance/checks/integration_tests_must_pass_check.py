# src/mind/governance/checks/integration_tests_must_pass_check.py
"""
Integration Tests Must Pass Governance Check

Enforces integration test gating rules declared in:
- .intent/charter/standards/operations/operations.(yaml|yml|json)
  (policy key commonly: "operations")

Targets:
- integration.tests_must_pass

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

RULE_INTEGRATION_TESTS_MUST_PASS = "integration.tests_must_pass"


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

    uniq = sorted({p.resolve() for p in candidates})
    return [Path(p) for p in uniq]


def _test_evidence_lines(text: str) -> list[str]:
    """
    Extract evidence lines indicating tests are executed as part of integration.

    Conservative acceptance:
    - explicit pytest invocation
    - make/tox targets that obviously run tests
    - CI job steps named test and executing a test runner
    """
    patterns = [
        r"\bpytest\b(\s|$)",
        r"\bpython\b\s+-m\s+pytest\b",
        r"\btox\b.*\b(py|test)\b",
        r"\bnox\b.*\btest\b",
        r"\bmake\b.*\btest(s)?\b",
        r"\buv\b\s+run\s+pytest\b",
        r"\bpoetry\b\s+run\s+pytest\b",
        r"\bpdm\b\s+run\s+pytest\b",
        # sometimes: core-admin integration pipeline includes tests
        r"\bcore-admin\b.*\b(integration|ci)\b.*\btest(s)?\b",
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


# ID: 3c1c46e8-4a8b-4c63-a409-2a0db9dd40d0
class IntegrationTestsMustPassEnforcement(EnforcementMethod):
    """
    Evidence-backed check for integration.tests_must_pass.

    Validation (conservative):
    1) Rule exists in operations policy.
    2) Gating evidence that tests are executed in integration:
       - Preferred: internal integration checker confirms it.
       - Fallback: CI/workflow files show explicit test runner execution.
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: 1f2d2b0a-2051-4ff3-9c69-7fd3b00d5d6b
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
                    message="Operations policy file missing; cannot validate integration.tests_must_pass.",
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
            (r for r in rules if r.get("id") == RULE_INTEGRATION_TESTS_MUST_PASS), None
        )
        if not this_rule:
            return [
                _create_finding_safe(
                    self,
                    message="integration.tests_must_pass rule not declared in operations policy.",
                    file_path=_rel(repo_path, policy_path),
                    severity=AuditSeverity.ERROR,
                )
            ]

        # Preferred: internal checker evidence
        internal = _try_run_internal_integration_checker(repo_path)
        if internal is not None:
            passed = bool(
                internal.get("tests_must_pass")
                or internal.get(RULE_INTEGRATION_TESTS_MUST_PASS)
                or internal.get("ok_tests")
            )
            if passed:
                return []

            return [
                _create_finding_safe(
                    self,
                    message="Internal integration checker did not confirm that tests are executed/passing as part of integration.",
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
                        "tests execution."
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
            evidence_lines = _test_evidence_lines(txt)
            if evidence_lines:
                hits.append({"file": _rel(repo_path, p), "evidence": evidence_lines})
            if len(hits) >= 5:
                break

        if not hits:
            return [
                _create_finding_safe(
                    self,
                    message=(
                        "CI/workflow files were found, but no clear evidence of test execution was detected "
                        "(e.g., 'pytest', 'python -m pytest', 'make test')."
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

        return []


# ID: 9a0c2b2d-57a9-4dd5-8f9c-5a0a412e9c77
class IntegrationTestsMustPassCheck(RuleEnforcementCheck):
    """
    Enforces integration.tests_must_pass via evidence-backed validation.
    """

    policy_rule_ids: ClassVar[list[str]] = [RULE_INTEGRATION_TESTS_MUST_PASS]

    policy_file: ClassVar[Path] = settings.paths.policy("operations")

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        IntegrationTestsMustPassEnforcement(
            rule_id=RULE_INTEGRATION_TESTS_MUST_PASS,
            severity=AuditSeverity.ERROR,
        )
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
