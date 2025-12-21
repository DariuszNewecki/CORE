# src/mind/governance/checks/symbols_public_api_check.py
"""
Symbols — Public Capability ID & Docstring Governance Check

Targets (policies/code/code_standards):
- symbols.public_capability_id_and_docstring

Intent
- Any *public* symbol (top-level function/class with a non-underscore name)
  must have:
  1) an explicit Capability/Symbol ID marker near its definition, and
  2) a docstring.

This is a CORE “public API hygiene” rule: public symbols are discoverable,
linkable, and governable only if they have stable IDs and documentation.

Design constraints
- Evidence-backed; never pretend-pass.
- Conservative static analysis (AST + nearby source scan).
- Policy-driven allowlists/exclusions supported (if present in rule_data).

Default heuristics (unless policy overrides)
- Public symbol = top-level ast.FunctionDef / ast.AsyncFunctionDef / ast.ClassDef
  where name does not start with "_".
- Docstring = ast.get_docstring(node) is not None and non-empty.
- ID marker = one of the following found in the N lines immediately above the
  definition (default N=8):
    - a UUID-like token: 8-4-4-4-12 hex
    - an "ID:" marker line (recommended style in CORE)

Scope (default)
- Scan src/**/*.py and scripts/**/*.py if present.
- Exclude tests/**, .venv/**, caches, and __init__.py.
"""

from __future__ import annotations

import ast
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

RULE_PUBLIC_CAPABILITY_ID_AND_DOCSTRING = "symbols.public_capability_id_and_docstring"

_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_ID_MARKER_RE = re.compile(r"\bID\s*:\s*", re.IGNORECASE)


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


@dataclass(frozen=True)
class _Violation:
    file: str
    line: int
    symbol_kind: str  # function | async_function | class
    name: str
    missing: list[str]  # ["id", "docstring"]
    context: dict[str, Any]


# ID: 2a4c8ea0-d545-417f-b7bc-b9c0fba215c5
class PublicSymbolIdAndDocstringEnforcement(EnforcementMethod):
    """
    Verifies that public (top-level) symbols have both:
    - an ID marker above the definition, and
    - a docstring.

    Optional policy knobs (rule_data):
    - include_roots: ["src", "scripts"]
    - exclude_globs: [...]
    - allowlist_globs: [...]
    - id_scan_lines: 8
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: 26e60312-fc29-4e3b-a16f-b732d5bdea54
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs: Any
    ) -> list[AuditFinding]:
        repo_path = context.repo_path

        include_roots = self._get_str_list(rule_data, "include_roots") or [
            "src",
            "scripts",
        ]
        exclude_globs = self._get_str_list(rule_data, "exclude_globs") or [
            "**/tests/**",
            "**/.venv/**",
            "**/.tox/**",
            "**/.mypy_cache/**",
            "**/.pytest_cache/**",
            "**/__pycache__/**",
            "**/site-packages/**",
        ]
        allowlist_globs = self._get_str_list(rule_data, "allowlist_globs") or []
        id_scan_lines = self._get_int(rule_data, "id_scan_lines", default=8)

        files = self._collect_files(repo_path, include_roots, exclude_globs)
        if not files:
            return [
                _create_finding_safe(
                    self,
                    message="No source files discovered in configured roots; cannot validate symbols.public_capability_id_and_docstring.",
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
            if relp.endswith("__init__.py"):
                continue
            if self._is_allowlisted(relp, allowlist_globs):
                continue

            try:
                src = p.read_text(encoding="utf-8")
                lines = src.splitlines()
                tree = ast.parse(src, filename=str(p))
            except Exception as exc:
                parse_errors.append({"file": relp, "error": str(exc)})
                continue

            violations.extend(self._scan_module(relp, lines, tree, id_scan_lines))

        if violations or parse_errors:
            return [
                _create_finding_safe(
                    self,
                    message="Public symbols missing required ID marker and/or docstring (or analysis errors).",
                    file_path="src",
                    severity=AuditSeverity.ERROR,
                    evidence={
                        "policy_file": (
                            str(
                                getattr(settings.paths, "policy", lambda *_: "unknown")(
                                    "code_standards"
                                )
                            )
                            if hasattr(settings, "paths")
                            else "unknown"
                        ),
                        "files_scanned": len(files),
                        "violations_count": len(violations),
                        "parse_errors_count": len(parse_errors),
                        "include_roots": include_roots,
                        "exclude_globs": exclude_globs,
                        "allowlist_globs": allowlist_globs,
                        "id_scan_lines": id_scan_lines,
                        "violations": [
                            {
                                "file": v.file,
                                "line": v.line,
                                "kind": v.symbol_kind,
                                "name": v.name,
                                "missing": v.missing,
                                "context": v.context,
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
    def _scan_module(
        self, rel_file: str, lines: list[str], tree: ast.Module, id_scan_lines: int
    ) -> list[_Violation]:
        out: list[_Violation] = []

        for node in getattr(tree, "body", []):
            if isinstance(node, ast.FunctionDef):
                out.extend(
                    self._inspect_symbol(
                        rel_file, lines, node, "function", id_scan_lines
                    )
                )
            elif isinstance(node, ast.AsyncFunctionDef):
                out.extend(
                    self._inspect_symbol(
                        rel_file, lines, node, "async_function", id_scan_lines
                    )
                )
            elif isinstance(node, ast.ClassDef):
                out.extend(
                    self._inspect_symbol(rel_file, lines, node, "class", id_scan_lines)
                )

        return out

    def _inspect_symbol(
        self,
        rel_file: str,
        lines: list[str],
        node: ast.AST,
        kind: str,
        id_scan_lines: int,
    ) -> list[_Violation]:
        name = getattr(node, "name", "")
        if not isinstance(name, str) or not name or name.startswith("_"):
            return []

        lineno = int(getattr(node, "lineno", 0) or 0)
        # lineno is 1-based
        header_start = max(0, lineno - 1 - id_scan_lines)
        header_end = max(0, lineno - 1)

        header_block = "\n".join(lines[header_start:header_end]).strip()
        has_id = bool(
            _UUID_RE.search(header_block) or _ID_MARKER_RE.search(header_block)
        )

        doc = (
            ast.get_docstring(node)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            else None
        )
        has_doc = bool(doc and str(doc).strip())

        missing: list[str] = []
        if not has_id:
            missing.append("id")
        if not has_doc:
            missing.append("docstring")

        if not missing:
            return []

        context: dict[str, Any] = {
            "header_scan": {
                "lines_above_scanned": id_scan_lines,
                "header_excerpt": self._excerpt_header(lines, header_start, header_end),
            },
            "docstring_present": has_doc,
        }

        return [
            _Violation(
                file=rel_file,
                line=lineno,
                symbol_kind=kind,
                name=name,
                missing=missing,
                context=context,
            )
        ]

    def _excerpt_header(self, lines: list[str], start: int, end: int) -> str:
        # Keep it short for evidence payload
        snippet_lines = lines[start:end][-10:]
        return "\n".join(snippet_lines).strip()

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

    def _get_int(self, d: dict[str, Any], key: str, *, default: int) -> int:
        v = d.get(key)
        try:
            if isinstance(v, int):
                return v
            if isinstance(v, str) and v.strip().isdigit():
                return int(v.strip())
        except Exception:
            return default
        return default


# ID: 8c2a7ac7-7f2e-4c6c-9b16-0c1f3e3e0c3a
class PublicSymbolsCheck(RuleEnforcementCheck):
    """
    Enforces public symbol hygiene:
    - Capability/Symbol ID marker above public symbol definitions
    - Docstrings for public symbol definitions

    Ref:
    - policies/code/code_standards
    """

    policy_rule_ids: ClassVar[list[str]] = [RULE_PUBLIC_CAPABILITY_ID_AND_DOCSTRING]

    # Policy binding should exist in PathResolver policies:
    # - .intent/policies/code/code_standards.(yaml|yml|json)
    policy_file: ClassVar[Path] = settings.paths.policy("code_standards")

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        PublicSymbolIdAndDocstringEnforcement(
            rule_id=RULE_PUBLIC_CAPABILITY_ID_AND_DOCSTRING,
            severity=AuditSeverity.ERROR,
        )
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
