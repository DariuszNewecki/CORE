# src/mind/governance/checks/body_contracts_check.py
"""
Body Contracts Governance Check

Enforces CORE Body contract rules declared in:
- .intent/policies/architecture/body_contracts.json

Targets the Body gaps reported by governance coverage.

ERROR rules:
- body.atomic_actions_use_actionresult
- body.no_print_or_input_in_body
- body.no_ui_imports_in_body
- body.write_defaults_false

WARN rules:
- body.actionresult_data_json_safe
- body.dependency_injection_preferred
- body.no_envvar_access_in_body

Design constraints:
- Prefer internal CORE capabilities first (Body checker modules / shared utilities).
- Fall back to conservative static analysis only if checker modules are unavailable.
- Evidence-backed output per rule (never "pretend pass" if analysis cannot run).
"""

from __future__ import annotations

import ast
import asyncio
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

# -----------------------------
# Rule IDs (must match .intent)
# -----------------------------
RULE_ATOMIC_ACTIONS_USE_ACTIONRESULT = "body.atomic_actions_use_actionresult"
RULE_NO_PRINT_OR_INPUT_IN_BODY = "body.no_print_or_input_in_body"
RULE_NO_UI_IMPORTS_IN_BODY = "body.no_ui_imports_in_body"
RULE_WRITE_DEFAULTS_FALSE = "body.write_defaults_false"

RULE_ACTIONRESULT_DATA_JSON_SAFE = "body.actionresult_data_json_safe"
RULE_DEPENDENCY_INJECTION_PREFERRED = "body.dependency_injection_preferred"
RULE_NO_ENVVAR_ACCESS_IN_BODY = "body.no_envvar_access_in_body"


# -----------------------------
# Local config / heuristics
# -----------------------------
_BODY_ROOT = settings.REPO_PATH / "src" / "body"
_CLI_ROOT = _BODY_ROOT / "cli"
_ACTIONS_ROOT = _BODY_ROOT / "actions"

# UI / interactive frameworks (disallowed in non-CLI Body code)
_FORBIDDEN_IMPORT_PREFIXES: tuple[str, ...] = (
    "streamlit",
    "tkinter",
    "PyQt",
    "PySide",
    "kivy",
    "prompt_toolkit",
    "inquirer",
    # CLI frameworks (disallowed in non-cli Body code)
    "click",
    "typer",
    "rich",
)

# print/input should not appear in non-cli Body code
_FORBIDDEN_CALLS: tuple[str, ...] = ("print", "input")

# ActionResult marker
_ACTIONRESULT_MARKERS: tuple[str, ...] = ("ActionResult",)

# write semantics markers
_WRITE_PARAM_NAMES: tuple[str, ...] = (
    "write",
    "allow_write",
    "allow_mutation",
    "mutate",
    "destructive",
)

# Environment variable access markers
_ENVVAR_ATTRS: tuple[str, ...] = ("environ",)  # os.environ

# DI preferred heuristic:
# Treat calls to classes ending in these as "service-like" instantiation
# (warn if created inside entrypoint and not passed via __init__)
_DI_CLASS_SUFFIXES: tuple[str, ...] = (
    "Client",
    "Service",
    "Repository",
    "Repo",
    "Session",
    "Engine",
    "Connector",
    "Gateway",
)


@dataclass(frozen=True)
class _AnalysisResult:
    """
    Internal analysis snapshot for evidence emission.

    Each list contains dict payloads suitable for AuditFinding.details/evidence.
    """

    ui_import_violations: list[dict[str, Any]]
    print_input_violations: list[dict[str, Any]]
    actionresult_violations: list[dict[str, Any]]
    write_default_violations: list[dict[str, Any]]

    envvar_violations: list[dict[str, Any]]
    actionresult_json_violations: list[dict[str, Any]]
    di_preferred_violations: list[dict[str, Any]]

    parsed_files: int
    parse_errors: int


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        return path.is_relative_to(root)  # py3.9+
    except Exception:
        return str(root) in str(path)


def _is_forbidden_import(module: str) -> bool:
    m = module.strip()
    return any(m == p or m.startswith(f"{p}.") for p in _FORBIDDEN_IMPORT_PREFIXES)


def _parse_file(p: Path) -> ast.AST | None:
    try:
        return ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
    except Exception:
        return None


def _call_name(call: ast.Call) -> str:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return ""


def _call_token(call: ast.Call) -> str:
    """
    Like _call_name, but preserves whether it was attribute-style:
      - os.getenv(...) -> ".getenv"
      - getenv(...) -> "getenv"
    """
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return f".{call.func.attr}"
    return ""


def _render_node(node: ast.AST | None) -> str:
    if node is None:
        return "None"
    try:
        return ast.unparse(node)
    except Exception:
        return node.__class__.__name__


def _collect_py_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*.py") if p.is_file())


def _is_literal_json_safe(node: ast.AST) -> bool:
    """
    Conservative JSON-safety heuristic:
    Accept only obvious literal-safe structures (dict/list/tuple of literals),
    primitive constants, and None/True/False.

    Anything else (Name, Call, Attribute, comprehension, etc.) is treated as "unknown"
    and flagged as not provably json-safe.
    """
    if isinstance(node, ast.Constant):
        return node.value is None or isinstance(node.value, (str, int, float, bool))
    if isinstance(node, ast.Dict):
        return all(
            (k is None or _is_literal_json_safe(k)) and _is_literal_json_safe(v)
            for k, v in zip(node.keys, node.values)
        )
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return all(_is_literal_json_safe(e) for e in node.elts)
    return False


def _analyze_body_contracts(repo_root: Path) -> _AnalysisResult:
    """
    Conservative, evidence-oriented AST analysis.

    Scope:
    - src/body/**/*.py excluding src/body/cli/** for UI imports + print/input + envvar usage
    - src/body/actions/**/*.py for ActionResult + write-defaults + json-safe ActionResult payload + DI preference
    """
    body_root = repo_root / "src" / "body"
    cli_root = body_root / "cli"
    actions_root = body_root / "actions"

    ui_import_violations: list[dict[str, Any]] = []
    print_input_violations: list[dict[str, Any]] = []
    actionresult_violations: list[dict[str, Any]] = []
    write_default_violations: list[dict[str, Any]] = []

    envvar_violations: list[dict[str, Any]] = []
    actionresult_json_violations: list[dict[str, Any]] = []
    di_preferred_violations: list[dict[str, Any]] = []

    parsed_files = 0
    parse_errors = 0

    # Non-CLI body files
    for f in _collect_py_files(body_root):
        if _is_relative_to(f, cli_root):
            continue

        tree = _parse_file(f)
        if tree is None:
            parse_errors += 1
            continue
        parsed_files += 1

        rel = str(f.relative_to(repo_root))

        # UI imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name or ""
                    if _is_forbidden_import(name):
                        ui_import_violations.append(
                            {"file": rel, "line": node.lineno, "import": name}
                        )
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if mod and _is_forbidden_import(mod):
                    ui_import_violations.append(
                        {"file": rel, "line": node.lineno, "import": mod}
                    )

        # print/input usage
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in _FORBIDDEN_CALLS:
                    print_input_violations.append(
                        {"file": rel, "line": node.lineno, "call": node.func.id}
                    )

        # envvar access markers:
        # 1) os.getenv(...)
        # 2) os.environ.get(...)
        # 3) os.environ["X"] (Subscript)
        # 4) from os import environ; environ.get(...) or environ["X"]
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                tok = _call_token(node)
                if tok in ("getenv", ".getenv"):
                    envvar_violations.append(
                        {"file": rel, "line": node.lineno, "pattern": tok}
                    )
                if isinstance(node.func, ast.Attribute) and node.func.attr == "get":
                    base = node.func.value
                    if isinstance(base, ast.Attribute) and base.attr in _ENVVAR_ATTRS:
                        envvar_violations.append(
                            {
                                "file": rel,
                                "line": node.lineno,
                                "pattern": "os.environ.get",
                            }
                        )
                    if isinstance(base, ast.Name) and base.id == "environ":
                        envvar_violations.append(
                            {
                                "file": rel,
                                "line": node.lineno,
                                "pattern": "environ.get",
                            }
                        )

            if isinstance(node, ast.Subscript):
                val = node.value
                if isinstance(val, ast.Attribute) and val.attr in _ENVVAR_ATTRS:
                    envvar_violations.append(
                        {
                            "file": rel,
                            "line": node.lineno,
                            "pattern": "os.environ[...]",
                        }
                    )
                if isinstance(val, ast.Name) and val.id == "environ":
                    envvar_violations.append(
                        {
                            "file": rel,
                            "line": node.lineno,
                            "pattern": "environ[...]",
                        }
                    )

    # Actions: ActionResult + write defaults + json-safe + DI preference
    for f in _collect_py_files(actions_root):
        tree = _parse_file(f)
        if tree is None:
            parse_errors += 1
            continue
        parsed_files += 1

        rel = str(f.relative_to(repo_root))

        # Heuristic: in classes, methods run/execute/invoke must return ActionResult(...)
        for cls in [
            n for n in getattr(tree, "body", []) if isinstance(n, ast.ClassDef)
        ]:
            entrypoints = [
                n
                for n in cls.body
                if isinstance(n, ast.FunctionDef)
                and n.name in ("run", "execute", "invoke")
            ]

            # Identify whether __init__ takes injected deps (anything beyond self)
            init_fns = [
                n
                for n in cls.body
                if isinstance(n, ast.FunctionDef) and n.name == "__init__"
            ]
            init_has_deps = False
            if init_fns:
                init_args = init_fns[0].args
                positional = list(init_args.posonlyargs) + list(init_args.args)
                if len(positional) > 1 or len(init_args.kwonlyargs) > 0:
                    init_has_deps = True

            # 1) ActionResult returns check
            for fn in entrypoints:
                returns = [n for n in ast.walk(fn) if isinstance(n, ast.Return)]
                if not returns:
                    actionresult_violations.append(
                        {
                            "file": rel,
                            "class": cls.name,
                            "method": fn.name,
                            "reason": "no_return",
                        }
                    )
                    continue

                for r in returns:
                    if r.value is None:
                        actionresult_violations.append(
                            {
                                "file": rel,
                                "class": cls.name,
                                "method": fn.name,
                                "line": r.lineno,
                                "return": "None",
                            }
                        )
                        continue
                    if (
                        isinstance(r.value, ast.Call)
                        and _call_name(r.value) in _ACTIONRESULT_MARKERS
                    ):
                        continue
                    actionresult_violations.append(
                        {
                            "file": rel,
                            "class": cls.name,
                            "method": fn.name,
                            "line": r.lineno,
                            "return": type(r.value).__name__,
                        }
                    )

            # 2) DI preferred: warn if entrypoint instantiates "service-like" classes and init has no deps
            for fn in entrypoints:
                for node in ast.walk(fn):
                    if not isinstance(node, ast.Call):
                        continue
                    name = _call_name(node)
                    if not name:
                        continue
                    if any(name.endswith(suf) for suf in _DI_CLASS_SUFFIXES):
                        if not init_has_deps:
                            di_preferred_violations.append(
                                {
                                    "file": rel,
                                    "class": cls.name,
                                    "method": fn.name,
                                    "line": getattr(node, "lineno", None),
                                    "instantiated": name,
                                    "reason": "instantiated_in_entrypoint_without_injected_deps",
                                }
                            )

            # 3) ActionResult data json-safe: check ActionResult(...) calls inside entrypoints
            for fn in entrypoints:
                for node in ast.walk(fn):
                    if not isinstance(node, ast.Call):
                        continue
                    if _call_name(node) not in _ACTIONRESULT_MARKERS:
                        continue

                    payload_nodes: list[tuple[str, ast.AST]] = []
                    for kw in node.keywords:
                        if (
                            kw.arg in ("data", "payload", "result")
                            and kw.value is not None
                        ):
                            payload_nodes.append((kw.arg, kw.value))

                    for key, val in payload_nodes:
                        if _is_literal_json_safe(val):
                            continue
                        actionresult_json_violations.append(
                            {
                                "file": rel,
                                "class": cls.name,
                                "method": fn.name,
                                "line": getattr(node, "lineno", None),
                                "field": key,
                                "value": _render_node(val),
                                "reason": "not_provably_json_safe_literal",
                            }
                        )

        # Heuristic: if a function/method defines write/mutation params, they must default to False.
        # ID: 753049d6-9a93-4397-9c1a-273ae4751fa3
        def inspect_fn(fn: ast.FunctionDef, owner: str | None) -> None:
            args = fn.args
            pos_args = list(args.posonlyargs) + list(args.args)
            kw_args = list(args.kwonlyargs)

            defaults = list(args.defaults)
            start = len(pos_args) - len(defaults)
            default_map: dict[str, ast.AST | None] = {}

            for i, a in enumerate(pos_args):
                default_map[a.arg] = defaults[i - start] if i >= start else None

            for a, d in zip(kw_args, args.kw_defaults):
                default_map[a.arg] = d

            for name, default_node in default_map.items():
                if name not in _WRITE_PARAM_NAMES:
                    continue

                if default_node is None:
                    write_default_violations.append(
                        {
                            "file": rel,
                            "owner": owner or "<module>",
                            "function": fn.name,
                            "param": name,
                            "default": "<missing>",
                        }
                    )
                    continue

                if (
                    isinstance(default_node, ast.Constant)
                    and default_node.value is False
                ):
                    continue

                write_default_violations.append(
                    {
                        "file": rel,
                        "owner": owner or "<module>",
                        "function": fn.name,
                        "param": name,
                        "default": _render_node(default_node),
                    }
                )

        for fn in [
            n for n in getattr(tree, "body", []) if isinstance(n, ast.FunctionDef)
        ]:
            inspect_fn(fn, None)

        for cls in [
            n for n in getattr(tree, "body", []) if isinstance(n, ast.ClassDef)
        ]:
            for fn in [n for n in cls.body if isinstance(n, ast.FunctionDef)]:
                inspect_fn(fn, cls.name)

    return _AnalysisResult(
        ui_import_violations=ui_import_violations,
        print_input_violations=print_input_violations,
        actionresult_violations=actionresult_violations,
        write_default_violations=write_default_violations,
        envvar_violations=envvar_violations,
        actionresult_json_violations=actionresult_json_violations,
        di_preferred_violations=di_preferred_violations,
        parsed_files=parsed_files,
        parse_errors=parse_errors,
    )


def _run_internal_checker_callable(fn: Any, repo_root: Path) -> Any:
    """
    Runs an internal checker callable in a sync-safe way.

    Critical behavior:
    - If the callable returns a coroutine, it is executed to completion to avoid
      'coroutine was never awaited' leaks.
    - This function is intended to be called from a SYNC context (RuleEnforcementCheck.execute),
      which is typically executed via asyncio.to_thread(...) by the auditor.
    """
    try:
        out = fn()
    except TypeError:
        out = fn(repo_root)

    if inspect.iscoroutine(out):
        # RuleEnforcementCheck.execute is sync; in practice the auditor calls it in a worker thread.
        # In that context there is no running loop, so asyncio.run is safe.
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(out)

        # If we ever end up inside a running loop (unexpected for this check), fail closed.
        raise RuntimeError(
            "Internal body contracts checker returned a coroutine while a loop is running. "
            "Callers must await it (or ensure this check runs in a worker thread)."
        )

    return out


def _try_internal_checker(repo_root: Path) -> list[dict[str, Any]] | None:
    """
    Attempt to reuse CORE's internal checker, if present.

    Accepted outputs:
    - list[dict] where dict contains rule_id/id + ok + message/detail (+ optional evidence)
    - object with attribute .findings (list[dict])
    """
    try:
        from body.cli.logic import body_contracts_checker as mod  # type: ignore
    except Exception:
        return None

    entrypoints = (
        "check",
        "run_check",
        "run",
        "analyze",
        "scan",
        "check_body_contracts",
    )

    fn = None
    for name in entrypoints:
        cand = getattr(mod, name, None)
        if callable(cand):
            fn = cand
            break

    if fn is None:
        return None

    try:
        out = _run_internal_checker_callable(fn, repo_root)
    except Exception:
        return None

    if isinstance(out, list) and all(isinstance(x, dict) for x in out):
        return out

    findings_attr = getattr(out, "findings", None)
    if isinstance(findings_attr, list) and all(
        isinstance(x, dict) for x in findings_attr
    ):
        return findings_attr

    return None


# =============================================================================
# Enforcement methods (one per rule)
# =============================================================================
class _BodyContractsBaseEnforcement(EnforcementMethod):
    """
    Shared enforcement base: tries internal checker first, falls back to AST analysis.

    IMPORTANT:
    - All findings must be created via self._create_finding(...) to match CORE's AuditFinding API.
    """

    _CACHE_ATTR = "_body_contracts_check_cache"

    def _load_analysis(self, context: AuditorContext) -> tuple[str, dict[str, Any]]:
        """
        Returns:
        - mode: 'internal_checker' or 'fallback_ast'
        - payload: normalized evidence payload for this run

        Uses a per-context cache to avoid re-running analysis N times (one per rule).
        """
        cache = getattr(context, self._CACHE_ATTR, None)
        if isinstance(cache, dict) and "mode" in cache and "payload" in cache:
            mode = cache["mode"]
            payload = cache["payload"]
            if isinstance(mode, str) and isinstance(payload, dict):
                return mode, payload

        repo_root = context.repo_path

        internal = _try_internal_checker(repo_root)
        if internal is not None:
            mode, payload = (
                "internal_checker",
                {
                    "source": "body.cli.logic.body_contracts_checker",
                    "raw_findings": internal,
                },
            )
            setattr(context, self._CACHE_ATTR, {"mode": mode, "payload": payload})
            return mode, payload

        analysis = _analyze_body_contracts(repo_root)
        mode, payload = (
            "fallback_ast",
            {
                "source": "ast",
                "parsed_files": analysis.parsed_files,
                "parse_errors": analysis.parse_errors,
                "ui_import_violations": analysis.ui_import_violations,
                "print_input_violations": analysis.print_input_violations,
                "actionresult_violations": analysis.actionresult_violations,
                "write_default_violations": analysis.write_default_violations,
                "envvar_violations": analysis.envvar_violations,
                "actionresult_json_violations": analysis.actionresult_json_violations,
                "di_preferred_violations": analysis.di_preferred_violations,
            },
        )
        setattr(context, self._CACHE_ATTR, {"mode": mode, "payload": payload})
        return mode, payload

    def _cannot_verify_finding(
        self,
        *,
        rule_id: str,
        mode: str,
        payload: dict[str, Any],
        message: str,
        file_path: str,
    ) -> list[AuditFinding]:
        """
        Helper: emit a finding when analysis cannot be performed reliably
        (e.g., no parsed files).
        """
        parsed_files = int(payload.get("parsed_files", 0) or 0)
        if parsed_files > 0:
            return []

        return [
            self._create_finding(
                message=message,
                file_path=file_path,
                details={
                    "mode": mode,
                    "rule_id": rule_id,
                    "source": payload.get("source"),
                    "parsed_files": payload.get("parsed_files"),
                    "parse_errors": payload.get("parse_errors"),
                },
            )
        ]


# ID: 2d561b29-88c7-49a9-ab23-36e8ce14f5f2
class AtomicActionsUseActionResultEnforcement(_BodyContractsBaseEnforcement):
    # ID: 67343041-55f9-4c38-820e-26c24571fc9f
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs: Any
    ) -> list[AuditFinding]:
        mode, payload = self._load_analysis(context)

        if mode == "internal_checker":
            raw = payload.get("raw_findings", [])
            violations = [
                f
                for f in raw
                if str(f.get("rule_id") or f.get("id") or "")
                == RULE_ATOMIC_ACTIONS_USE_ACTIONRESULT
                and not bool(f.get("ok", False))
            ]
            if not violations:
                return []
            return [
                self._create_finding(
                    message="Atomic actions must return ActionResult (violations reported by internal checker).",
                    file_path=str(Path(context.repo_path).name),
                    details={"mode": mode, "violations": violations},
                )
            ]

        cannot = self._cannot_verify_finding(
            rule_id=RULE_ATOMIC_ACTIONS_USE_ACTIONRESULT,
            mode=mode,
            payload=payload,
            message="Cannot verify ActionResult contract: no parseable Body modules were analyzed.",
            file_path="src/body",
        )
        if cannot:
            return cannot

        violations = payload.get("actionresult_violations", [])
        if not violations:
            return []
        return [
            self._create_finding(
                message="Atomic action entrypoints appear to return non-ActionResult values.",
                file_path="src/body/actions",
                details={"mode": mode, "violations": violations[:200]},
            )
        ]


# ID: 91812b33-8c4a-47dc-bc4c-acc37adbe42b
class NoPrintOrInputInBodyEnforcement(_BodyContractsBaseEnforcement):
    # ID: 8fecb2cd-6158-4426-968f-76fd8180e0f6
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs: Any
    ) -> list[AuditFinding]:
        mode, payload = self._load_analysis(context)

        if mode == "internal_checker":
            raw = payload.get("raw_findings", [])
            violations = [
                f
                for f in raw
                if str(f.get("rule_id") or f.get("id") or "")
                == RULE_NO_PRINT_OR_INPUT_IN_BODY
                and not bool(f.get("ok", False))
            ]
            if not violations:
                return []
            return [
                self._create_finding(
                    message="Body code must not use print()/input() (violations reported by internal checker).",
                    file_path=str(Path(context.repo_path).name),
                    details={"mode": mode, "violations": violations},
                )
            ]

        cannot = self._cannot_verify_finding(
            rule_id=RULE_NO_PRINT_OR_INPUT_IN_BODY,
            mode=mode,
            payload=payload,
            message="Cannot verify print()/input() prohibition: no parseable Body modules were analyzed.",
            file_path="src/body",
        )
        if cannot:
            return cannot

        violations = payload.get("print_input_violations", [])
        if not violations:
            return []
        return [
            self._create_finding(
                message="Non-CLI Body code uses print()/input() (disallowed).",
                file_path="src/body",
                details={"mode": mode, "violations": violations[:200]},
            )
        ]


# ID: 02047f81-4db9-46ea-923b-2703925a022e
class NoUiImportsInBodyEnforcement(_BodyContractsBaseEnforcement):
    # ID: 00624666-ca75-46ef-8380-d3c33310acfc
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs: Any
    ) -> list[AuditFinding]:
        mode, payload = self._load_analysis(context)

        if mode == "internal_checker":
            raw = payload.get("raw_findings", [])
            violations = [
                f
                for f in raw
                if str(f.get("rule_id") or f.get("id") or "")
                == RULE_NO_UI_IMPORTS_IN_BODY
                and not bool(f.get("ok", False))
            ]
            if not violations:
                return []
            return [
                self._create_finding(
                    message="Body code must not import UI/interactive dependencies (violations reported by internal checker).",
                    file_path=str(Path(context.repo_path).name),
                    details={"mode": mode, "violations": violations},
                )
            ]

        cannot = self._cannot_verify_finding(
            rule_id=RULE_NO_UI_IMPORTS_IN_BODY,
            mode=mode,
            payload=payload,
            message="Cannot verify UI import prohibition: no parseable Body modules were analyzed.",
            file_path="src/body",
        )
        if cannot:
            return cannot

        violations = payload.get("ui_import_violations", [])
        if not violations:
            return []
        return [
            self._create_finding(
                message="Non-CLI Body code imports UI/interactive dependencies (disallowed).",
                file_path="src/body",
                details={"mode": mode, "violations": violations[:200]},
            )
        ]


# ID: a0ce3804-fbb6-4efc-b9a0-61522287d3f7
class WriteDefaultsFalseEnforcement(_BodyContractsBaseEnforcement):
    # ID: ca6c4dbd-af9b-4afd-9c4f-3be87198615b
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs: Any
    ) -> list[AuditFinding]:
        mode, payload = self._load_analysis(context)

        if mode == "internal_checker":
            raw = payload.get("raw_findings", [])
            violations = [
                f
                for f in raw
                if str(f.get("rule_id") or f.get("id") or "")
                == RULE_WRITE_DEFAULTS_FALSE
                and not bool(f.get("ok", False))
            ]
            if not violations:
                return []
            return [
                self._create_finding(
                    message="Write/mutation parameters must default to False (violations reported by internal checker).",
                    file_path=str(Path(context.repo_path).name),
                    details={"mode": mode, "violations": violations},
                )
            ]

        cannot = self._cannot_verify_finding(
            rule_id=RULE_WRITE_DEFAULTS_FALSE,
            mode=mode,
            payload=payload,
            message="Cannot verify write-defaults contract: no parseable actions were analyzed.",
            file_path="src/body/actions",
        )
        if cannot:
            return cannot

        violations = payload.get("write_default_violations", [])
        if not violations:
            return []
        return [
            self._create_finding(
                message="Write/mutation parameters do not default to False in atomic actions.",
                file_path="src/body/actions",
                details={"mode": mode, "violations": violations[:200]},
            )
        ]


# ID: 1f18819d-61c1-4c16-a3ec-a802f61976f6
class NoEnvvarAccessInBodyEnforcement(_BodyContractsBaseEnforcement):
    # ID: 20d046a1-f74c-4432-9692-c16522e1d121
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs: Any
    ) -> list[AuditFinding]:
        mode, payload = self._load_analysis(context)

        if mode == "internal_checker":
            raw = payload.get("raw_findings", [])
            violations = [
                f
                for f in raw
                if str(f.get("rule_id") or f.get("id") or "")
                == RULE_NO_ENVVAR_ACCESS_IN_BODY
                and not bool(f.get("ok", False))
            ]
            if not violations:
                return []
            return [
                self._create_finding(
                    message="Body code should not access environment variables directly (internal checker evidence).",
                    file_path=str(Path(context.repo_path).name),
                    details={"mode": mode, "violations": violations},
                )
            ]

        cannot = self._cannot_verify_finding(
            rule_id=RULE_NO_ENVVAR_ACCESS_IN_BODY,
            mode=mode,
            payload=payload,
            message="Cannot verify envvar-access rule: no parseable Body modules were analyzed.",
            file_path="src/body",
        )
        if cannot:
            return cannot

        violations = payload.get("envvar_violations", [])
        if not violations:
            return []
        return [
            self._create_finding(
                message="Non-CLI Body code accesses environment variables directly (prefer RuntimeSettings/DI).",
                file_path="src/body",
                details={"mode": mode, "violations": violations[:200]},
            )
        ]


# ID: a8d8e4c9-ea56-433f-8790-596aea58a332
class ActionResultDataJsonSafeEnforcement(_BodyContractsBaseEnforcement):
    # ID: 23b8accd-0aaf-47b4-84c5-37cecfed2ef6
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs: Any
    ) -> list[AuditFinding]:
        mode, payload = self._load_analysis(context)

        if mode == "internal_checker":
            raw = payload.get("raw_findings", [])
            violations = [
                f
                for f in raw
                if str(f.get("rule_id") or f.get("id") or "")
                == RULE_ACTIONRESULT_DATA_JSON_SAFE
                and not bool(f.get("ok", False))
            ]
            if not violations:
                return []
            return [
                self._create_finding(
                    message="ActionResult payloads should be JSON-safe (internal checker evidence).",
                    file_path=str(Path(context.repo_path).name),
                    details={"mode": mode, "violations": violations},
                )
            ]

        cannot = self._cannot_verify_finding(
            rule_id=RULE_ACTIONRESULT_DATA_JSON_SAFE,
            mode=mode,
            payload=payload,
            message="Cannot verify ActionResult JSON-safety: no parseable actions were analyzed.",
            file_path="src/body/actions",
        )
        if cannot:
            return cannot

        violations = payload.get("actionresult_json_violations", [])
        if not violations:
            return []
        return [
            self._create_finding(
                message=(
                    "Some ActionResult payloads are not provably JSON-safe "
                    "(use primitives / dict/list literals or serialize explicitly)."
                ),
                file_path="src/body/actions",
                details={"mode": mode, "violations": violations[:200]},
            )
        ]


# ID: 291e8c99-a735-4df7-939c-ba9462dfc0a0
class DependencyInjectionPreferredEnforcement(_BodyContractsBaseEnforcement):
    # ID: 8d30d8e3-905b-4679-9fe1-288d531dbb68
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs: Any
    ) -> list[AuditFinding]:
        mode, payload = self._load_analysis(context)

        if mode == "internal_checker":
            raw = payload.get("raw_findings", [])
            violations = [
                f
                for f in raw
                if str(f.get("rule_id") or f.get("id") or "")
                == RULE_DEPENDENCY_INJECTION_PREFERRED
                and not bool(f.get("ok", False))
            ]
            if not violations:
                return []
            return [
                self._create_finding(
                    message="Dependency injection is preferred in Body actions (internal checker evidence).",
                    file_path=str(Path(context.repo_path).name),
                    details={"mode": mode, "violations": violations},
                )
            ]

        cannot = self._cannot_verify_finding(
            rule_id=RULE_DEPENDENCY_INJECTION_PREFERRED,
            mode=mode,
            payload=payload,
            message="Cannot verify DI preference: no parseable actions were analyzed.",
            file_path="src/body/actions",
        )
        if cannot:
            return cannot

        violations = payload.get("di_preferred_violations", [])
        if not violations:
            return []
        return [
            self._create_finding(
                message="Some atomic actions instantiate service-like dependencies inside entrypoints; prefer injecting via __init__.",
                file_path="src/body/actions",
                details={"mode": mode, "violations": violations[:200]},
            )
        ]


# =============================================================================
# Check binding
# =============================================================================
# ID: cc50628a-d803-4c48-9c79-d46c87177bb8
class BodyContractsCheck(RuleEnforcementCheck):
    """
    Enforces Body contract rules with evidence-backed methods.

    Ref: .intent/policies/architecture/body_contracts.json
    """

    policy_rule_ids: ClassVar[list[str]] = [
        RULE_ATOMIC_ACTIONS_USE_ACTIONRESULT,
        RULE_NO_PRINT_OR_INPUT_IN_BODY,
        RULE_NO_UI_IMPORTS_IN_BODY,
        RULE_WRITE_DEFAULTS_FALSE,
        RULE_ACTIONRESULT_DATA_JSON_SAFE,
        RULE_DEPENDENCY_INJECTION_PREFERRED,
        RULE_NO_ENVVAR_ACCESS_IN_BODY,
    ]

    # NOTE: legacy shim is acceptable during migration; RuleEnforcementCheck resolves SSOT.
    policy_file: ClassVar = settings.paths.policy("body_contracts")

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        # ERROR
        AtomicActionsUseActionResultEnforcement(
            rule_id=RULE_ATOMIC_ACTIONS_USE_ACTIONRESULT,
            severity=AuditSeverity.ERROR,
        ),
        NoPrintOrInputInBodyEnforcement(
            rule_id=RULE_NO_PRINT_OR_INPUT_IN_BODY,
            severity=AuditSeverity.ERROR,
        ),
        NoUiImportsInBodyEnforcement(
            rule_id=RULE_NO_UI_IMPORTS_IN_BODY,
            severity=AuditSeverity.ERROR,
        ),
        WriteDefaultsFalseEnforcement(
            rule_id=RULE_WRITE_DEFAULTS_FALSE,
            severity=AuditSeverity.ERROR,
        ),
        # WARN
        ActionResultDataJsonSafeEnforcement(
            rule_id=RULE_ACTIONRESULT_DATA_JSON_SAFE,
            severity=AuditSeverity.WARNING,
        ),
        DependencyInjectionPreferredEnforcement(
            rule_id=RULE_DEPENDENCY_INJECTION_PREFERRED,
            severity=AuditSeverity.WARNING,
        ),
        NoEnvvarAccessInBodyEnforcement(
            rule_id=RULE_NO_ENVVAR_ACCESS_IN_BODY,
            severity=AuditSeverity.WARNING,
        ),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
