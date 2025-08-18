# src/system/tools/intent_guard_runner.py
"""
Intent Guard Runner

What it does
------------
1) Reads .intent/meta.yaml to find policy + source map.
2) Parses Python files under enabled domains and collects imports (AST-based).
3) Enforces .intent/policies/intent_guard.yaml:
   - deny-by-default between domains unless allowed
   - explicit forbids (e.g., agents -> system, core -> data)
   - disallow domain cycles in observed edges (if enabled)
   - library forbids (e.g., requests)
   - respects ignored paths and waivers
   - respects domains with enabled: false in source_structure.yaml

Usage
-----
PYTHONPATH=src poetry run python src/system/tools/intent_guard_runner.py check
# optional flags:
#   --format pretty|json  (default: pretty)
#   --no-fail             (exit 0 even if violations; overrides enforcement.mode)

Exit codes
----------
0 on success (or --no-fail); 1 if violations and enforcement.mode == "fail".
"""

from __future__ import annotations

import ast
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

import yaml

# Optional pretty output
try:
    from rich import box
    from rich.console import Console
    from rich.table import Table
except Exception:  # pragma: no cover
    Console = None
    Table = None
    box = None

# --- Paths -------------------------------------------------------------------


def find_repo_root(start: Optional[Path] = None) -> Path:
    here = (start or Path(__file__).resolve()).parent
    for p in [here] + list(here.parents):
        if (p / ".intent").exists():
            return p
    return Path.cwd()


REPO = find_repo_root()
INTENT = REPO / ".intent"
META = INTENT / "meta.yaml"

# --- Models ------------------------------------------------------------------


@dataclass
class Domain:
    name: str
    path: Path
    enabled: bool


@dataclass
class ImportEdge:
    importer_file: Path
    importer_domain: str
    imported_module: str
    imported_domain: Optional[str]
    lineno: Optional[int]


# --- Helpers -----------------------------------------------------------------


def load_yaml(path: Path) -> dict:
    if not path.exists():
        fail(f"Missing file: {rel(path)}")
    try:
        return yaml.safe_load(path.read_text()) or {}
    except Exception as e:
        fail(f"YAML error in {rel(path)}: {e}")


def rel(p: Path) -> str:
    try:
        return str(p.relative_to(REPO))
    except Exception:
        return str(p)


def info(msg: str) -> None:
    if Console:
        Console().print(f"[bold cyan]INFO[/] {msg}")
    else:
        print(f"INFO {msg}")


def warn(msg: str) -> None:
    if Console:
        Console().print(f"[bold yellow]WARN[/] {msg}")
    else:
        print(f"WARN {msg}")


def fail(msg: str, code: int = 1) -> None:
    if Console:
        Console().print(f"[bold red]ERROR[/] {msg}")
    else:
        print(f"ERROR {msg}", file=sys.stderr)
    sys.exit(code)


def compile_regex_list(patterns: Iterable[str]) -> List[re.Pattern]:
    out = []
    for p in patterns or []:
        try:
            out.append(re.compile(p))
        except re.error as e:
            warn(f"Invalid regex '{p}': {e}")
    return out


def path_matches_any(path: str, patterns: List[re.Pattern]) -> bool:
    return any(r.search(path) for r in patterns)


def is_relative_import(node: ast.AST) -> bool:
    # from .foo import bar  OR  from .. import x
    return isinstance(node, ast.ImportFrom) and (node.level or 0) > 0


# --- Policy & map loading ----------------------------------------------------


def load_paths_from_meta() -> Tuple[Path, Path]:
    meta = load_yaml(META)
    pol = meta.get("policies", {})
    knowledge = meta.get("knowledge", {})
    policy_path = INTENT / pol.get("intent_guard", "policies/intent_guard.yaml")
    source_map_path = INTENT / knowledge.get(
        "source_structure", "knowledge/source_structure.yaml"
    )
    return policy_path, source_map_path


def load_domains(source_map_path: Path) -> Dict[str, Domain]:
    data = load_yaml(source_map_path)
    out: Dict[str, Domain] = {}
    for d in data.get("domains", []):
        name = d.get("domain")
        if not name:
            continue
        path = REPO / str(d.get("path", ""))
        out[name] = Domain(name=name, path=path, enabled=bool(d.get("enabled", True)))
    return out


# --- Scanner -----------------------------------------------------------------


def discover_py_files(
    domains: Dict[str, Domain], ignored: List[re.Pattern]
) -> List[Path]:
    files: List[Path] = []
    for dom in domains.values():
        if not dom.enabled:
            continue
        base = dom.path
        if not base.exists():
            # Don't fail: domain may be declared ahead of time
            continue
        for p in base.rglob("*.py"):
            rp = rel(p)
            if path_matches_any(rp, ignored):
                continue
            files.append(p)
    return files


def top_level_name(mod: str) -> str:
    return mod.split(".", 1)[0]


def resolve_domain_for_module(mod: str, domains: Dict[str, Domain]) -> Optional[str]:
    tl = top_level_name(mod)
    if tl in domains:
        return tl
    return None  # 3rd-party or stdlib


def scan_file_imports(path: Path) -> List[Tuple[str, Optional[int]]]:
    """Return list of (imported_module, lineno). Only absolute imports are returned."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as e:
        warn(f"Skipping {rel(path)} due to syntax error: {e}")
        return []
    out: List[Tuple[str, Optional[int]]] = []
    for node in ast.walk(tree):
        if is_relative_import(node):
            continue
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name:
                    out.append((alias.name, getattr(node, "lineno", None)))
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.append((node.module, getattr(node, "lineno", None)))
    return out


def domain_for_file(path: Path, domains: Dict[str, Domain]) -> Optional[str]:
    for name, dom in domains.items():
        try:
            if path.is_relative_to(dom.path):
                return name
        except AttributeError:
            # Python <3.9 compatibility: emulate is_relative_to
            try:
                path.relative_to(dom.path)
                return name
            except Exception:
                pass
    return None


def collect_edges(
    domains: Dict[str, Domain], ignored: List[re.Pattern]
) -> List[ImportEdge]:
    edges: List[ImportEdge] = []
    for f in discover_py_files(domains, ignored):
        importer_dom = domain_for_file(f, domains)
        if not importer_dom:
            continue
        for mod, ln in scan_file_imports(f):
            imported_dom = resolve_domain_for_module(mod, domains)
            edges.append(
                ImportEdge(
                    importer_file=f,
                    importer_domain=importer_dom,
                    imported_module=mod,
                    imported_domain=imported_dom,
                    lineno=ln,
                )
            )
    return edges


# --- Enforcement -------------------------------------------------------------


@dataclass
class Violation:
    kind: str  # "forbidden-import" | "not-allowed" | "cycle" | "forbidden-library"
    message: str
    file: Optional[str] = None
    lineno: Optional[int] = None
    domain_from: Optional[str] = None
    domain_to: Optional[str] = None
    module: Optional[str] = None
    reason: Optional[str] = None


def enforce_policy(
    policy: dict,
    domains: Dict[str, Domain],
    edges: List[ImportEdge],
) -> List[Violation]:
    rules = policy.get("rules") or {}
    imports_rule = rules.get("imports") or {}
    libraries_rule = rules.get("libraries") or {}
    #    subprocess_rule = rules.get("subprocess") or {}  # reserved for future use

    # Respect enabled:false domains?
    respect_enabled = bool(imports_rule.get("respect_source_structure_enabled", False))

    # domain permissions
    domain_perms = imports_rule.get("domains") or {}
    default_policy = (imports_rule.get("default_policy") or "deny").lower()

    # forbids
    forbids = imports_rule.get("forbidden") or []
    forbid_pairs = {
        (f["from"], f["to"]): f.get("rationale")
        for f in forbids
        if "from" in f and "to" in f
    }

    # libraries
    lib_forbidden = set((libraries_rule.get("forbidden") or []))
    ignore_stdlib_prefixes = tuple(libraries_rule.get("ignore_stdlib_prefixes") or [])

    # ignored paths & waivers
    enforcement = policy.get("enforcement") or {}
    ignored_patterns = compile_regex_list(enforcement.get("ignored_paths") or [])
    waivers = enforcement.get("waivers") or []
    waiver_patterns = [
        (compile_regex_list([w.get("path", "")])[0], w.get("reason", ""))
        for w in waivers
        if w.get("path")
    ]

    violations: List[Violation] = []

    # 1) Domain-to-domain import checks
    for e in edges:
        rp = rel(e.importer_file)
        # Skip ignored paths
        if path_matches_any(rp, ignored_patterns):
            continue
        # Skip if either domain is disabled and we respect it
        if respect_enabled:
            if e.imported_domain and not domains[e.imported_domain].enabled:
                continue
            if e.importer_domain and not domains[e.importer_domain].enabled:
                continue

        # 1a) Library forbids (applies to 3rd-party too)
        if e.imported_domain is None:
            top = top_level_name(e.imported_module)
            if top.startswith(ignore_stdlib_prefixes):
                pass
            elif top in lib_forbidden:
                violations.append(
                    Violation(
                        kind="forbidden-library",
                        message=f"Use of forbidden library '{top}'",
                        file=rp,
                        lineno=e.lineno,
                        module=top,
                    )
                )
            # else: policy 'allow' → do nothing
            continue  # only domain edges below

        # 1b) Explicit forbids
        key = (e.importer_domain, e.imported_domain)
        if key in forbid_pairs:
            violations.append(
                Violation(
                    kind="forbidden-import",
                    message=f"{e.importer_domain} → {e.imported_domain} is forbidden",
                    file=rp,
                    lineno=e.lineno,
                    domain_from=e.importer_domain,
                    domain_to=e.imported_domain,
                    module=e.imported_module,
                    reason=forbid_pairs[key],
                )
            )
            continue

        # 1c) Default deny unless allowed
        allowed = set((domain_perms.get(e.importer_domain) or {}).get("may_import", []))
        if e.imported_domain not in allowed:
            if default_policy == "deny" and e.imported_domain != e.importer_domain:
                violations.append(
                    Violation(
                        kind="not-allowed",
                        message=f"{e.importer_domain} may not import {e.imported_domain}",
                        file=rp,
                        lineno=e.lineno,
                        domain_from=e.importer_domain,
                        domain_to=e.imported_domain,
                        module=e.imported_module,
                    )
                )

    # 2) Cycle detection across observed domain edges
    if imports_rule.get("disallow_cycles", False):
        graph: Dict[str, Set[str]] = {}
        for e in edges:
            if (
                e.imported_domain
                and e.importer_domain
                and e.imported_domain != e.importer_domain
            ):
                # Respect enabled: skip disabled edges
                if respect_enabled and (
                    not domains[e.importer_domain].enabled
                    or not domains[e.imported_domain].enabled
                ):
                    continue
                graph.setdefault(e.importer_domain, set()).add(e.imported_domain)
        cycles = find_domain_cycles(graph)
        for cyc in cycles:
            # Represent cycle compactly: A→B→...→A
            cycle_str = " → ".join(cyc + [cyc[0]])
            violations.append(
                Violation(
                    kind="cycle",
                    message=f"Domain import cycle detected: {cycle_str}",
                    domain_from=cyc[0],
                    domain_to=cyc[-1],
                )
            )

    # 3) Apply waivers (suppress by file regex)
    if waiver_patterns:
        filtered: List[Violation] = []
        for v in violations:
            rp = v.file or ""
            waived = any(r.search(rp) for r, _ in waiver_patterns)
            if not waived:
                filtered.append(v)
        violations = filtered

    return violations


def find_domain_cycles(graph: Dict[str, Set[str]]) -> List[List[str]]:
    """Return list of cycles found in a directed graph (domain-level)."""
    visited: Set[str] = set()
    stack: Set[str] = set()
    path: List[str] = []
    cycles: List[List[str]] = []

    def dfs(node: str):
        visited.add(node)
        stack.add(node)
        path.append(node)
        for nbr in graph.get(node, set()):
            if nbr not in visited:
                dfs(nbr)
            elif nbr in stack:
                # Found a cycle; slice path from nbr to end
                try:
                    i = path.index(nbr)
                    cyc = path[i:].copy()
                    if cyc and cyc not in cycles:
                        cycles.append(cyc)
                except ValueError:
                    pass
        stack.remove(node)
        path.pop()

    for n in list(graph.keys()):
        if n not in visited:
            dfs(n)
    return cycles


# --- Reporting ---------------------------------------------------------------


def print_report(violations: List[Violation], fmt: str = "pretty") -> None:
    if not violations:
        if Console:
            Console().print("[bold green]✅ No guard violations.[/]")
        else:
            print("OK: No guard violations.")
        return

    if fmt == "json":
        print(json.dumps([v.__dict__ for v in violations], indent=2))
        return

    # pretty
    if Console and Table:
        console = Console()
        table = Table(title="Intent Guard Violations", box=box.SIMPLE_HEAVY)
        table.add_column("Kind")
        table.add_column("From")
        table.add_column("To/Module")
        table.add_column("File:Line")
        table.add_column("Reason/Msg")
        for v in violations:
            from_d = v.domain_from or "-"
            to = v.domain_to or (v.module or "-")
            fl = f"{v.file}:{v.lineno}" if v.file else "-"
            reason = v.reason or v.message
            table.add_row(v.kind, from_d, to, fl, reason)
        console.print(table)
    else:
        print("Violations:")
        for v in violations:
            print(
                f"- [{v.kind}] {v.domain_from or '-'} -> {v.domain_to or v.module or '-'} "
                f"at {v.file}:{v.lineno} :: {v.reason or v.message}"
            )


# --- CLI ---------------------------------------------------------------------


def parse_args(argv: List[str]) -> Tuple[str, Dict[str, str]]:
    if not argv:
        return "check", {"format": "pretty", "no_fail": "0"}
    cmd = argv[0]
    fmt = "pretty"
    no_fail = "0"
    for a in argv[1:]:
        if a == "--format" and False:
            pass  # reserved
        elif a.startswith("--format="):
            fmt = a.split("=", 1)[1].strip()
        elif a == "--no-fail":
            no_fail = "1"
        elif a in {"pretty", "json"}:
            fmt = a
        else:
            # ignore unknowns to stay friendly
            pass
    if cmd not in {"check"}:
        fail(f"Unknown command '{cmd}'. Use: check [--format=json|pretty] [--no-fail]")
    return cmd, {"format": fmt, "no_fail": no_fail}


def main(argv: Optional[List[str]] = None) -> None:
    cmd, opts = parse_args(argv or sys.argv[1:])
    fmt = opts.get("format", "pretty")
    no_fail_flag = opts.get("no_fail") == "1"

    policy_path, source_map_path = load_paths_from_meta()
    policy = load_yaml(policy_path)
    #    source_map = load_yaml(source_map_path)

    # enforcement.mode: warn|fail
    enforcement = policy.get("enforcement") or {}
    mode_fail = (enforcement.get("mode", "fail").lower() == "fail") and (
        not no_fail_flag
    )

    # compile ignore patterns once
    ignored = compile_regex_list(enforcement.get("ignored_paths") or [])

    domains = load_domains(source_map_path)
    edges = collect_edges(domains, ignored)
    violations = enforce_policy(policy, domains, edges)

    print_report(violations, fmt=fmt)

    if violations and mode_fail:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
