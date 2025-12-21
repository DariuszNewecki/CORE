# src/mind/governance/checks/safety_execution_primitives_check.py
"""
Safety — Dangerous Execution Primitives Governance Check

Targets (standard_operations_safety):
- safety.no_dangerous_execution_primitives

Purpose
- Prevent introduction of code-execution / shell-execution primitives that
  undermine CORE safety guarantees (especially in Body and tooling layers).

Design constraints
- Evidence-backed. No pretend-pass.
- Conservative static analysis (AST) with minimal false positives.
- Policy-driven allowlists are supported (if present in rule_data).

What we flag (default set; extend via policy later):
- builtins: eval(), exec(), compile()
- subprocess: subprocess.run/call/check_call/check_output/Popen
- os: os.system(), os.popen(), os.spawn*()
- importlib: import_module() (optional; currently NOT flagged by default)

Scope (default)
- Scan src/**/*.py and scripts/**/*.py if present.
- Exclude common virtualenv/cache folders.
"""

from __future__ import annotations

import ast
import fnmatch
import inspect
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

RULE_NO_DANGEROUS_EXECUTION_PRIMITIVES = "safety.no_dangerous_execution_primitives"


# --- Policy resolution (robust) ------------------------------------------------
def _resolve_policy_file() -> Path:
    """
    Try the canonical policy resolver first, then fall back to conventional paths.
    """
    repo = settings.REPO_PATH
    candidates: list[Path] = []

    # Preferred key (most likely)
    try:
        return settings.paths.policy("operations_safety")
    except Exception:
        pass

    # Secondary key (some repos use shorter names)
    try:
        return settings.paths.policy("safety")
    except Exception:
        pass

    # Conventional fallbacks
    candidates.extend(
        [
            repo / ".intent" / "charter" / "standards" / "operations" / "safety.yaml",
            repo / ".intent" / "charter" / "standards" / "operations" / "safety.yml",
            repo / ".intent" / "policies" / "operations" / "safety.yaml",
            repo / ".intent" / "policies" / "operations" / "safety.yml",
            repo / ".intent" / "policies" / "operations" / "operations_safety.yaml",
            repo / ".intent" / "policies" / "operations" / "operations_safety.yml",
        ]
    )

    for p in candidates:
        if p.exists():
            return p

    # Last resort (non-existent but stable path)
    return candidates[0]


_POLICY_FILE = _resolve_policy_file()


# --- Finding helper (signature-safe) -------------------------------------------
def _create_finding_safe(method: EnforcementMethod, **kwargs: Any) -> AuditFinding:
    """
    EnforcementMethod._create_finding() signature varies across CORE versions.

    Only pass supported parameters to avoid runtime TypeError.
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


# --- Static analysis model ------------------------------------------------------
@dataclass(frozen=True)
class _Violation:
    file: str
    line: int
    kind: str
    symbol: str
    snippet: str


# --- Enforcement method ---------------------------------------------------------
# ID: 8af2c90c-d7cf-485c-a557-3891fe47e1a4
class NoDangerousExecutionPrimitivesEnforcement(EnforcementMethod):
    """
    Scans Python sources for dangerous execution primitives.

    Policy-driven knobs (optional; read from rule_data if present):
    - include_roots: ["src", "scripts"] (default)
    - exclude_globs: ["**/tests/**", ...] (default minimal)
    - allowlist_globs: ["src/body/cli/**"] (default none)
    - forbidden:
        - builtins: ["eval", "exec", "compile"]
        - modules:
            - os: ["system", "popen", "spawnl", ...]
            - subprocess: ["run", "Popen", ...]
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: 0834a436-1910-4c25-9a5f-96e7030e44b6
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs: Any
    ) -> list[AuditFinding]:
        repo_path = context.repo_path

        include_roots = self._get_str_list(rule_data, "include_roots") or [
            "src",
            "scripts",
        ]
        exclude_globs = self._get_str_list(rule_data, "exclude_globs") or [
            "**/.venv/**",
            "**/.tox/**",
            "**/.mypy_cache/**",
            "**/.pytest_cache/**",
            "**/__pycache__/**",
            "**/site-packages/**",
        ]
        allowlist_globs = self._get_str_list(rule_data, "allowlist_globs") or []

        forbidden = rule_data.get("forbidden") if isinstance(rule_data, dict) else None
        builtins = ["eval", "exec", "compile"]
        os_calls = [
            "system",
            "popen",
            "spawnl",
            "spawnle",
            "spawnlp",
            "spawnlpe",
            "spawnv",
            "spawnve",
            "spawnvp",
            "spawnvpe",
        ]
        subprocess_calls = ["run", "call", "check_call", "check_output", "Popen"]

        if isinstance(forbidden, dict):
            fb = forbidden.get("builtins")
            if isinstance(fb, list) and all(isinstance(x, str) for x in fb):
                builtins = fb

            mods = forbidden.get("modules")
            if isinstance(mods, dict):
                oc = mods.get("os")
                sc = mods.get("subprocess")
                if isinstance(oc, list) and all(isinstance(x, str) for x in oc):
                    os_calls = oc
                if isinstance(sc, list) and all(isinstance(x, str) for x in sc):
                    subprocess_calls = sc

        files = self._collect_files(repo_path, include_roots, exclude_globs)
        if not files:
            return [
                _create_finding_safe(
                    self,
                    message="No source files discovered in configured roots; cannot validate safety.no_dangerous_execution_primitives.",
                    file_path=";".join(include_roots),
                    severity=AuditSeverity.ERROR,
                    evidence={
                        "include_roots": include_roots,
                        "exclude_globs": exclude_globs,
                        "repo_path": str(repo_path),
                    },
                )
            ]

        violations: list[_Violation] = []
        parse_errors: list[dict[str, Any]] = []

        for p in files:
            relp = _rel(repo_path, p)

            if self._is_allowlisted(relp, allowlist_globs):
                continue

            try:
                src = p.read_text(encoding="utf-8")
                tree = ast.parse(src, filename=str(p))
            except Exception as exc:
                parse_errors.append({"file": relp, "error": str(exc)})
                continue

            violations.extend(
                self._scan_tree(tree, relp, builtins, os_calls, subprocess_calls)
            )

        if violations or parse_errors:
            return [
                _create_finding_safe(
                    self,
                    message="Dangerous execution primitives detected (or analysis errors).",
                    file_path="src",
                    severity=AuditSeverity.ERROR,
                    evidence={
                        "policy_file": str(_POLICY_FILE),
                        "files_scanned": len(files),
                        "violations_count": len(violations),
                        "parse_errors_count": len(parse_errors),
                        "allowlist_globs": allowlist_globs,
                        "forbidden": {
                            "builtins": builtins,
                            "modules": {"os": os_calls, "subprocess": subprocess_calls},
                        },
                        "violations": [
                            {
                                "file": v.file,
                                "line": v.line,
                                "kind": v.kind,
                                "symbol": v.symbol,
                                "snippet": v.snippet,
                            }
                            for v in violations[:200]
                        ],
                        "parse_errors": parse_errors[:50],
                    },
                )
            ]

        return []

    # -------------------------
    # Scanning
    # -------------------------
    def _scan_tree(
        self,
        tree: ast.AST,
        rel_file: str,
        builtins: list[str],
        os_calls: list[str],
        subprocess_calls: list[str],
    ) -> list[_Violation]:
        out: list[_Violation] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            kind, symbol = self._classify_call(
                node, builtins, os_calls, subprocess_calls
            )
            if not kind:
                continue

            out.append(
                _Violation(
                    file=rel_file,
                    line=getattr(node, "lineno", 0) or 0,
                    kind=kind,
                    symbol=symbol,
                    snippet=self._render_call(node),
                )
            )
        return out

    def _classify_call(
        self,
        node: ast.Call,
        builtins: list[str],
        os_calls: list[str],
        subprocess_calls: list[str],
    ) -> tuple[str, str]:
        # builtins: eval()/exec()/compile()
        if isinstance(node.func, ast.Name) and node.func.id in set(builtins):
            return ("builtin_execution", node.func.id)

        # module.attr patterns: os.system, subprocess.Popen, subprocess.run, etc.
        if isinstance(node.func, ast.Attribute):
            base = node.func.value
            attr = node.func.attr

            if isinstance(base, ast.Name) and base.id == "os" and attr in set(os_calls):
                return ("os_execution", f"os.{attr}")

            if (
                isinstance(base, ast.Name)
                and base.id == "subprocess"
                and attr in set(subprocess_calls)
            ):
                return ("subprocess_execution", f"subprocess.{attr}")

        return ("", "")

    def _render_call(self, node: ast.Call) -> str:
        try:
            return ast.unparse(node)
        except Exception:
            # Minimal fallback
            if isinstance(node.func, ast.Name):
                return f"{node.func.id}(...)"
            if isinstance(node.func, ast.Attribute):
                return f"{node.func.attr}(...)"
            return "call(...)"

    # -------------------------
    # File discovery
    # -------------------------
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
                relp = _rel(repo_path, p)
                if self._matches_any(relp, exclude_globs):
                    continue
                out.append(p)
        return sorted(out)

    def _matches_any(self, rel_path: str, globs: list[str]) -> bool:
        norm = rel_path.replace("\\", "/")
        return any(fnmatch.fnmatch(norm, g) for g in globs)

    def _is_allowlisted(self, rel_path: str, allowlist_globs: list[str]) -> bool:
        if not allowlist_globs:
            return False
        norm = rel_path.replace("\\", "/")
        return any(fnmatch.fnmatch(norm, g) for g in allowlist_globs)

    # -------------------------
    # Rule-data parsing
    # -------------------------
    def _get_str_list(self, d: dict[str, Any], key: str) -> list[str]:
        v = d.get(key)
        if isinstance(v, list):
            return [str(x) for x in v if str(x).strip()]
        if isinstance(v, str) and v.strip():
            return [v.strip()]
        return []


# --- Check wrapper --------------------------------------------------------------
# ID: 4f0c7d0e-1e7c-4c4d-9f50-1c8e2474ab11
class SafetyExecutionPrimitivesCheck(RuleEnforcementCheck):
    """
    Enforces safety constraints around dangerous code execution primitives.

    Ref:
    - standard_operations_safety
    """

    policy_rule_ids: ClassVar[list[str]] = [RULE_NO_DANGEROUS_EXECUTION_PRIMITIVES]
    policy_file: ClassVar[Path] = Path(_POLICY_FILE)

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        NoDangerousExecutionPrimitivesEnforcement(
            rule_id=RULE_NO_DANGEROUS_EXECUTION_PRIMITIVES,
            severity=AuditSeverity.ERROR,
        )
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
