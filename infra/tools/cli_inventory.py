#!/usr/bin/env python3
"""
CLI Inventory for CORE.

Discovers Typer-based commands by parsing CLI registration code.
Outputs:
- artifacts/cli_inventory.json
- artifacts/cli_inventory.md
"""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"

ENTRYPOINTS = [
    ("core-admin", SRC_ROOT / "body" / "cli" / "admin_cli.py"),
]

RESOURCE_DIR = SRC_ROOT / "body" / "cli" / "resources"
COMMANDS_DIR = SRC_ROOT / "body" / "cli" / "commands"

OUTPUT_JSON = REPO_ROOT / "artifacts" / "cli_inventory.json"
OUTPUT_MD = REPO_ROOT / "artifacts" / "cli_inventory.md"


@dataclass
class CommandInfo:
    app_var: str
    command_name: str
    handler_name: str | None
    handler_module: str | None
    file_path: Path
    lineno: int
    evidence: list[str]
    is_deprecated_wrapper: bool = False


@dataclass
class AddTyperInfo:
    parent_app_var: str
    subapp_var: str | None
    subapp_base: str | None
    subapp_attr: str | None
    name: str | None
    file_path: Path
    lineno: int
    evidence: list[str]
    source_line: str
    arg0_dump: str | None
    arg0_locals: list[str]


@dataclass
class ModuleInfo:
    module_name: str
    file_path: Path
    app_vars: set[str]
    commands: list[CommandInfo]
    add_typers: list[AddTyperInfo]
    import_map: dict[str, str]  # local name -> module path (best effort)
    command_lists: dict[str, list[dict[str, Any]]]  # list_name -> entries


class ASTScanner(ast.NodeVisitor):
    def __init__(
        self, file_path: Path, module_name: str, source: str, tree: ast.AST
    ) -> None:
        self.file_path = file_path
        self.module_name = module_name
        self.source = source
        self.is_pkg_init = file_path.name == "__init__.py"
        self.app_vars: set[str] = set()
        self.commands: list[CommandInfo] = []
        self.add_typers: list[AddTyperInfo] = []
        self.import_map: dict[str, str] = {}
        self.command_lists: dict[str, list[dict[str, Any]]] = {}
        self._parents: dict[int, ast.AST] = {}
        self._lines = source.splitlines()
        self._build_parent_map(tree)

    def _build_parent_map(self, tree: ast.AST) -> None:
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                self._parents[id(child)] = parent

    def _parent(self, node: ast.AST) -> ast.AST | None:
        return self._parents.get(id(node))

    def _line_snippet(self, lineno: int) -> str:
        if 1 <= lineno <= len(self._lines):
            return self._lines[lineno - 1].strip()
        return ""

    def _line_raw(self, lineno: int) -> str:
        if 1 <= lineno <= len(self._lines):
            return self._lines[lineno - 1].rstrip("\n")
        return ""

    def visit_ImportFrom(self, node: ast.ImportFrom) -> Any:
        mod = node.module or ""
        level = node.level or 0
        if self.is_pkg_init and level >= 1:
            parts = self.module_name.split(".")
            if level > 1:
                drop = level - 1
                if drop >= len(parts):
                    base = []
                else:
                    base = parts[:-drop]
            else:
                base = parts
            if mod:
                base.extend(mod.split("."))
            resolved = ".".join(base)
        else:
            resolved = resolve_relative_module(self.module_name, mod, level)
        for alias in node.names:
            local = alias.asname or alias.name
            # Store fully-qualified symbol path
            if resolved:
                self.import_map[local] = f"{resolved}.{alias.name}"
            else:
                self.import_map[local] = alias.name
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> Any:
        for alias in node.names:
            local = alias.asname or alias.name
            self.import_map[local] = alias.name
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> Any:
        # Detect app = typer.Typer(...)
        try:
            if isinstance(node.value, ast.Call):
                func = node.value.func
                if (
                    isinstance(func, ast.Attribute)
                    and isinstance(func.value, ast.Name)
                    and func.attr == "Typer"
                    and func.value.id in {"typer", "Typer"}
                ):
                    for t in node.targets:
                        if isinstance(t, ast.Name):
                            self.app_vars.add(t.id)
        except Exception:
            pass
        # Detect *_commands = [ {"name": "...", "func": ...}, ... ]
        try:
            if isinstance(node.value, ast.List):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id.endswith("_commands"):
                        entries = []
                        for elt in node.value.elts:
                            if not isinstance(elt, ast.Dict):
                                continue
                            name_val = None
                            func_val = None
                            for k, v in zip(elt.keys, elt.values):
                                if isinstance(k, ast.Constant) and k.value == "name":
                                    if isinstance(v, ast.Constant) and isinstance(
                                        v.value, str
                                    ):
                                        name_val = v.value
                                if isinstance(k, ast.Constant) and k.value == "func":
                                    if isinstance(v, ast.Name):
                                        func_val = v.id
                            if name_val and func_val:
                                entries.append(
                                    {
                                        "name": name_val,
                                        "func": func_val,
                                        "lineno": getattr(
                                            elt, "lineno", getattr(node, "lineno", 1)
                                        ),
                                    }
                                )
                        if entries:
                            self.command_lists[t.id] = entries
        except Exception:
            pass
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        # Decorator-based commands: @app.command(...)
        for dec in node.decorator_list:
            cmd = self._command_from_decorator(dec, node)
            if cmd:
                self.commands.append(cmd)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        # Decorator-based commands
        for dec in node.decorator_list:
            cmd = self._command_from_decorator(dec, node)
            if cmd:
                self.commands.append(cmd)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> Any:
        # app.command()(handler) pattern
        cmd = self._command_from_call_chain(node)
        if cmd:
            self.commands.append(cmd)
        # app.add_typer(subapp, name="...")
        add = self._add_typer_from_call(node)
        if add:
            self.add_typers.append(add)
        self.generic_visit(node)

    def _command_from_decorator(self, dec: ast.AST, fn: ast.AST) -> CommandInfo | None:
        if not isinstance(dec, ast.Call):
            return None
        func = dec.func
        if not (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.attr == "command"
        ):
            return None
        app_var = func.value.id
        command_name = extract_command_name(dec) or getattr(fn, "name", "")
        handler_name = getattr(fn, "name", None)
        evidence = [
            f"{self.file_path}:{getattr(fn, 'lineno', 1)} {self._line_snippet(getattr(fn, 'lineno', 1))}"
        ]
        return CommandInfo(
            app_var=app_var,
            command_name=command_name,
            handler_name=handler_name,
            handler_module=self.module_name,
            file_path=self.file_path,
            lineno=getattr(fn, "lineno", 1),
            evidence=evidence,
            is_deprecated_wrapper=contains_deprecated_call(fn),
        )

    def _command_from_call_chain(self, node: ast.Call) -> CommandInfo | None:
        # Identify app.command()(handler)
        parent = self._parent(node)
        if not (isinstance(node.func, ast.Attribute) and node.func.attr == "command"):
            return None
        if not isinstance(node.func.value, ast.Name):
            return None
        if not (isinstance(parent, ast.Call) and parent.func is node):
            return None
        app_var = node.func.value.id
        command_name = extract_command_name(node) or ""
        handler_name = None
        handler_module = None
        if parent.args:
            arg0 = parent.args[0]
            if isinstance(arg0, ast.Name):
                handler_name = arg0.id
            elif isinstance(arg0, ast.Attribute):
                handler_name = arg0.attr
        if handler_name and handler_name in self.import_map:
            handler_module = self.import_map[handler_name]
        evidence = [
            f"{self.file_path}:{getattr(node, 'lineno', 1)} {self._line_snippet(getattr(node, 'lineno', 1))}",
            f"{self.file_path}:{getattr(parent, 'lineno', 1)} {self._line_snippet(getattr(parent, 'lineno', 1))}",
        ]
        return CommandInfo(
            app_var=app_var,
            command_name=command_name or handler_name or "",
            handler_name=handler_name,
            handler_module=handler_module or self.module_name,
            file_path=self.file_path,
            lineno=getattr(parent, "lineno", 1),
            evidence=evidence,
            is_deprecated_wrapper=False,
        )

    def _add_typer_from_call(self, node: ast.Call) -> AddTyperInfo | None:
        if not (isinstance(node.func, ast.Attribute) and node.func.attr == "add_typer"):
            return None
        if not isinstance(node.func.value, ast.Name):
            return None
        parent_app = node.func.value.id
        subapp_var = None
        subapp_base = None
        subapp_attr = None
        arg0_dump = None
        arg0_locals: list[str] = []
        if node.args:
            arg0 = node.args[0]
            arg0_dump = ast.dump(arg0, include_attributes=False)
            names = {n.id for n in ast.walk(arg0) if isinstance(n, ast.Name)}
            arg0_locals = sorted(names)
            if isinstance(arg0, ast.Name):
                subapp_var = arg0.id
                subapp_base = arg0.id
            elif isinstance(arg0, ast.Attribute):
                if isinstance(arg0.value, ast.Name):
                    subapp_base = arg0.value.id
                subapp_attr = arg0.attr
        name = None
        for kw in node.keywords:
            if kw.arg == "name" and isinstance(kw.value, ast.Constant):
                name = str(kw.value.value)
        if not (subapp_var or subapp_base):
            return None
        lineno = getattr(node, "lineno", 1)
        evidence = [f"{self.file_path}:{lineno} {self._line_snippet(lineno)}"]
        source_line = self._line_raw(lineno)
        return AddTyperInfo(
            parent_app_var=parent_app,
            subapp_var=subapp_var,
            subapp_base=subapp_base,
            subapp_attr=subapp_attr,
            name=name,
            file_path=self.file_path,
            lineno=lineno,
            evidence=evidence,
            source_line=source_line,
            arg0_dump=arg0_dump,
            arg0_locals=arg0_locals,
        )


def contains_deprecated_call(fn_node: ast.AST) -> bool:
    for n in ast.walk(fn_node):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
            if n.func.id == "deprecated_command":
                return True
    return False


def extract_command_name(call: ast.Call) -> str | None:
    # app.command("name") or app.command(name="name")
    if call.args:
        arg0 = call.args[0]
        if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
            return arg0.value
    for kw in call.keywords:
        if kw.arg == "name" and isinstance(kw.value, ast.Constant):
            return str(kw.value.value)
    return None


def resolve_relative_module(current_module: str, module: str, level: int) -> str:
    if level == 0:
        return module
    parts = current_module.split(".")
    # current_module includes file module; remove that for package base
    pkg = parts[:-1] if parts else []
    if level > 1:
        drop = level - 1
        if drop >= len(pkg):
            base = []
        else:
            base = pkg[:-drop]
    else:
        base = pkg
    if module:
        base.extend(module.split("."))
    return ".".join(base)


def module_name_from_path(path: Path) -> str:
    rel = path.relative_to(SRC_ROOT)
    parts = rel.with_suffix("").parts
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def split_import_target(target: str) -> tuple[str, str | None]:
    if "." not in target:
        return target, None
    module, symbol = target.rsplit(".", 1)
    return module, symbol


def scan_file(path: Path) -> ModuleInfo | None:
    try:
        source = path.read_text(encoding="utf-8")
    except Exception:
        return None
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    module_name = module_name_from_path(path)
    scanner = ASTScanner(path, module_name, source, tree)
    scanner.visit(tree)
    return ModuleInfo(
        module_name=module_name,
        file_path=path,
        app_vars=scanner.app_vars,
        commands=scanner.commands,
        add_typers=scanner.add_typers,
        import_map=scanner.import_map,
        command_lists=scanner.command_lists,
    )


def scan_tree(root: Path) -> list[ModuleInfo]:
    modules: list[ModuleInfo] = []
    for path in root.rglob("*.py"):
        mod = scan_file(path)
        if mod:
            modules.append(mod)
    return modules


def build_index(modules: list[ModuleInfo]) -> dict[str, ModuleInfo]:
    return {m.module_name: m for m in modules}


def resolve_handler(module: ModuleInfo, cmd: CommandInfo) -> tuple[str, bool]:
    # Best effort: module:handler
    if cmd.handler_name is None:
        return f"{module.module_name}:<unknown>", True
    # If handler is imported, try to resolve module
    if cmd.handler_name in module.import_map:
        target = module.import_map[cmd.handler_name]
        mod, sym = split_import_target(target)
        if sym:
            return f"{mod}:{sym}", False
        return f"{mod}:{cmd.handler_name}", False
    return f"{module.module_name}:{cmd.handler_name}", False


def expand_imported_command_lists(
    mod_info: ModuleInfo, index: dict[str, ModuleInfo], owner_app_var: str
) -> list[CommandInfo]:
    extra: list[CommandInfo] = []
    for local_name, mod_path in mod_info.import_map.items():
        if not local_name.endswith("_commands"):
            continue
        mod_only, _ = split_import_target(mod_path)
        target = index.get(mod_only)
        if not target:
            continue
        entries = target.command_lists.get(local_name, [])
        for ent in entries:
            handler_name = ent.get("func")
            if not handler_name:
                continue
            lineno = int(ent.get("lineno") or 1)
            if target.file_path.exists():
                line = target.file_path.read_text(encoding="utf-8").splitlines()
                snippet = line[lineno - 1].strip() if 1 <= lineno <= len(line) else ""
            else:
                snippet = ""
            evidence = [f"{target.file_path}:{lineno} {snippet}"]
            extra.append(
                CommandInfo(
                    app_var=owner_app_var,
                    command_name=ent.get("name", ""),
                    handler_name=handler_name,
                    handler_module=target.module_name,
                    file_path=target.file_path,
                    lineno=lineno,
                    evidence=evidence,
                    is_deprecated_wrapper=False,
                )
            )
    return extra


def resolve_app_node(mod_info: ModuleInfo, app_var: str) -> tuple[str, str]:
    if app_var in mod_info.import_map:
        target = mod_info.import_map[app_var]
        mod, sym = split_import_target(target)
        if sym:
            return mod, sym
        return mod, app_var
    return mod_info.module_name, app_var


def is_resource_module(path: Path) -> bool:
    try:
        path.relative_to(RESOURCE_DIR)
        return True
    except Exception:
        return False


def classify_command(
    is_resource: bool,
    is_legacy_alias: bool,
    is_deprecated_wrapper: bool,
) -> str:
    if is_legacy_alias or is_deprecated_wrapper:
        return "shim"
    if is_resource:
        return "native"
    return "needs_conversion"


def recommend_resource(command_group: str) -> str:
    mapping = {
        "check": "code",
        "inspect": "code",
        "fix": "code",
        "status": "code",
        "coverage": "code",
        "refactor": "code",
        "diagnostics": "code",
        "governance": "constitution",
        "mind": "constitution",
        "submit": "proposals",
        "dev": "dev",
        "project": "project",
    }
    return mapping.get(command_group, "code")


def summarize_counts(entries: list[dict[str, Any]]) -> dict[str, int]:
    native = shim = needs = total = 0
    for entry in entries:
        for r in entry.get("resources", []):
            for a in r.get("actions", []):
                total += 1
                if a["classification"] == "native":
                    native += 1
                elif a["classification"] == "shim":
                    shim += 1
                else:
                    needs += 1
        for n in entry.get("non_resource_commands", []):
            total += 1
            if n["classification"] == "shim":
                shim += 1
            else:
                needs += 1
    return {
        "total_commands": total,
        "native": native,
        "shim": shim,
        "needs_conversion": needs,
    }


def main() -> None:
    modules = scan_tree(SRC_ROOT / "body" / "cli")
    index = build_index(modules)

    entrypoints = []
    conversion_backlog = []
    stats = {
        "apps_found": 0,
        "edges_found": 0,
        "commands_found": 0,
        "unresolved_edges": 0,
        "unresolved_handlers": 0,
    }
    unresolved_edge_details: list[dict[str, Any]] = []

    for entry_name, entry_file in ENTRYPOINTS:
        entry_module = module_name_from_path(entry_file)
        entry_info = index.get(entry_module)
        if not entry_info:
            continue

        # Build graph nodes
        app_nodes = {(m.module_name, v) for m in modules for v in m.app_vars}
        stats["apps_found"] = len(app_nodes)

        # Resolve add_typer edges
        edges = []
        unresolved_edges = 0
        unresolved_edge_details = []
        for mi in modules:
            for add in mi.add_typers:
                parent_var = add.parent_app_var
                if parent_var not in mi.app_vars and "app" in mi.app_vars:
                    parent_var = "app"
                parent = (mi.module_name, parent_var)
                base = add.subapp_base or add.subapp_var
                if not base:
                    unresolved_edges += 1
                    unresolved_edge_details.append(
                        {
                            "file_path": add.file_path,
                            "lineno": add.lineno,
                            "source_line": add.source_line,
                            "arg0_dump": add.arg0_dump,
                            "arg0_locals": add.arg0_locals,
                            "import_hits": {
                                name: mi.import_map.get(name)
                                for name in add.arg0_locals
                                if name in mi.import_map
                            },
                        }
                    )
                    continue
                if base in mi.app_vars:
                    mod = mi.module_name
                    sym = base
                else:
                    target = mi.import_map.get(base)
                    if not target:
                        unresolved_edges += 1
                        unresolved_edge_details.append(
                            {
                                "file_path": add.file_path,
                                "lineno": add.lineno,
                                "source_line": add.source_line,
                                "arg0_dump": add.arg0_dump,
                                "arg0_locals": add.arg0_locals,
                                "import_hits": {
                                    name: mi.import_map.get(name)
                                    for name in add.arg0_locals
                                    if name in mi.import_map
                                },
                            }
                        )
                        continue
                    mod, sym = split_import_target(target)
                    if not mod:
                        unresolved_edges += 1
                        unresolved_edge_details.append(
                            {
                                "file_path": add.file_path,
                                "lineno": add.lineno,
                                "source_line": add.source_line,
                                "arg0_dump": add.arg0_dump,
                                "arg0_locals": add.arg0_locals,
                                "import_hits": {
                                    name: mi.import_map.get(name)
                                    for name in add.arg0_locals
                                    if name in mi.import_map
                                },
                            }
                        )
                        continue
                child_app = None
                if add.subapp_attr:
                    if mod in index and add.subapp_attr in index[mod].app_vars:
                        child_app = add.subapp_attr
                    elif sym and mod in index and sym in index[mod].app_vars:
                        child_app = sym
                    else:
                        child_app = add.subapp_attr
                else:
                    child_app = sym or base

                if mod in index:
                    if (
                        child_app not in index[mod].app_vars
                        and "app" in index[mod].app_vars
                    ):
                        child_app = "app"

                child = (mod, child_app)
                edge_name = add.name or child_app or base
                edges.append({"parent": parent, "child": child, "name": edge_name})
        stats["edges_found"] = len(edges)
        stats["unresolved_edges"] = unresolved_edges

        # Determine root app var
        root_app = (
            "app"
            if "app" in entry_info.app_vars
            else next(iter(entry_info.app_vars), None)
        )
        if root_app is None:
            continue
        root_node = (entry_info.module_name, root_app)

        # Build adjacency and BFS paths
        adj = {}
        for e in edges:
            adj.setdefault(e["parent"], []).append(e)

        from collections import deque

        path_map = {root_node: []}
        q = deque([root_node])
        while q:
            node = q.popleft()
            for e in adj.get(node, []):
                child = e["child"]
                if child not in path_map:
                    path_map[child] = path_map[node] + [e["name"]]
                    q.append(child)

        # Resource groups are add_typer names directly under root that point to resources modules
        resource_groups: dict[str, str] = {}
        for e in edges:
            if e["parent"] != root_node or not e["name"]:
                continue
            child_mod, _ = e["child"]
            if child_mod.startswith("body.cli.resources."):
                resource_groups[e["name"]] = child_mod
        resource_names = set(resource_groups.keys())

        resources_out = []
        non_resource_out = []
        resources_index = {}

        # Collect commands from all modules
        for mi in modules:
            owner_app = next(iter(mi.app_vars), "app")
            all_cmds = list(mi.commands)
            all_cmds.extend(
                expand_imported_command_lists(mi, index, owner_app_var=owner_app)
            )

            for cmd in all_cmds:
                node = resolve_app_node(mi, cmd.app_var)
                if node not in path_map:
                    continue
                path = path_map[node]
                if not cmd.command_name:
                    continue
                full_parts = [entry_name] + path + [cmd.command_name]
                command_path = " ".join([p for p in full_parts if p]).strip()

                is_resource = len(path) >= 1 and path[0] in resource_names
                is_legacy = len(path) >= 1 and path[0].startswith("legacy-")
                classification = classify_command(
                    is_resource=is_resource,
                    is_legacy_alias=is_legacy,
                    is_deprecated_wrapper=cmd.is_deprecated_wrapper,
                )

                handler, unresolved_handler = resolve_handler(mi, cmd)
                handler_mod = handler.split(":", 1)[0]
                if handler_mod not in index:
                    unresolved_handler = True
                if unresolved_handler:
                    stats["unresolved_handlers"] += 1

                stats["commands_found"] += 1

                entry = {
                    "command": command_path,
                    "handler": handler,
                    "classification": classification,
                    "evidence": cmd.evidence,
                }

                if is_resource:
                    res_name = path[0]
                    if res_name not in resources_index:
                        res_mod = resource_groups.get(res_name, "")
                        res_module = (
                            str(index[res_mod].file_path)
                            if res_mod in index
                            else res_mod
                        )
                        resources_index[res_name] = {
                            "resource": res_name,
                            "module": res_module,
                            "actions": [],
                        }
                    resources_index[res_name]["actions"].append(entry)
                else:
                    non_entry = {
                        "command": command_path,
                        "module": str(mi.file_path),
                        "handler": handler,
                        "classification": classification,
                        "evidence": cmd.evidence,
                    }
                    non_resource_out.append(non_entry)
                    if classification == "needs_conversion":
                        group = path[0] if path else "(root)"
                        conversion_backlog.append(
                            {
                                "command": command_path,
                                "current_location": str(mi.file_path),
                                "recommended_target_resource": recommend_resource(
                                    group
                                ),
                                "recommended_action_name": cmd.command_name,
                                "notes": "Non-resource CLI group; consider migrating under resource module",
                            }
                        )

        resources_out = list(resources_index.values())

        entrypoints.append(
            {
                "name": entry_name,
                "file": str(entry_file),
                "framework": "typer",
                "resources": resources_out,
                "non_resource_commands": non_resource_out,
            }
        )

    summary_counts = summarize_counts(entrypoints)
    resources_total = sum(len(e.get("resources", [])) for e in entrypoints)
    summary = {**summary_counts, "resources_total": resources_total}

    output = {
        "generated_at": datetime.now(UTC).isoformat(),
        "entrypoints": entrypoints,
        "summary": summary,
        "conversion_backlog": conversion_backlog,
        "discovery_stats": stats,
    }
    OUTPUT_JSON.write_text(json.dumps(output, indent=2), encoding="utf-8")

    # Markdown report
    md_lines = []
    md_lines.append("# CLI Inventory")
    md_lines.append("")
    md_lines.append("## Summary")
    md_lines.append("")
    md_lines.append("| Metric | Count |")
    md_lines.append("|---|---:|")
    md_lines.append(f"| Total commands | {summary['total_commands']} |")
    md_lines.append(f"| Native (resource) | {summary['native']} |")
    md_lines.append(f"| Shim | {summary['shim']} |")
    md_lines.append(f"| Needs conversion | {summary['needs_conversion']} |")
    md_lines.append(f"| Resources total | {summary['resources_total']} |")

    md_lines.append("")
    md_lines.append("## Discovery Coverage")
    md_lines.append("")
    md_lines.append("| Stat | Count |")
    md_lines.append("|---|---:|")
    md_lines.append(f"| Apps found | {stats['apps_found']} |")
    md_lines.append(f"| Edges found | {stats['edges_found']} |")
    md_lines.append(f"| Commands found | {stats['commands_found']} |")
    md_lines.append(f"| Unresolved edges | {stats['unresolved_edges']} |")
    md_lines.append(f"| Unresolved handler refs | {stats['unresolved_handlers']} |")

    # Counts by resource
    md_lines.append("")
    md_lines.append("## Counts By Resource")
    md_lines.append("")
    md_lines.append("| Resource | Actions |")
    md_lines.append("|---|---:|")
    for entry in entrypoints:
        for res in entry.get("resources", []):
            md_lines.append(f"| {res['resource']} | {len(res.get('actions', []))} |")

    # One section per resource
    for entry in entrypoints:
        for res in entry.get("resources", []):
            md_lines.append("")
            md_lines.append(f"## Resource: {res['resource']}")
            md_lines.append("")
            md_lines.append("| Command | Handler | Classification | Evidence |")
            md_lines.append("|---|---|---|---|")
            for action in res.get("actions", []):
                ev = "; ".join(action.get("evidence", [])[:2])
                md_lines.append(
                    f"| `{action['command']}` | `{action['handler']}` | {action['classification']} | {ev} |"
                )

    # Non-resource commands
    md_lines.append("")
    md_lines.append("## Non-Resource Commands")
    md_lines.append("")
    md_lines.append("| Command | Module | Handler | Classification | Evidence |")
    md_lines.append("|---|---|---|---|---|")
    for entry in entrypoints:
        for cmd in entry.get("non_resource_commands", []):
            ev = "; ".join(cmd.get("evidence", [])[:2])
            md_lines.append(
                f"| `{cmd['command']}` | `{cmd['module']}` | `{cmd['handler']}` | {cmd['classification']} | {ev} |"
            )

    # Top 10 conversion candidates
    md_lines.append("")
    md_lines.append("## Top 10 Conversion Candidates")
    md_lines.append("")
    top_candidates = conversion_backlog[:10]
    if not top_candidates:
        md_lines.append("No conversion candidates found.")
    else:
        md_lines.append(
            "| Command | Current Location | Target Resource | Action | Notes |"
        )
        md_lines.append("|---|---|---|---|---|")
        for c in top_candidates:
            md_lines.append(
                f"| `{c['command']}` | `{c['current_location']}` | {c['recommended_target_resource']} | {c['recommended_action_name']} | {c['notes']} |"
            )

    OUTPUT_MD.write_text("\n".join(md_lines), encoding="utf-8")

    print(
        "Discovery stats: "
        f"apps={stats['apps_found']} "
        f"edges={stats['edges_found']} "
        f"commands={stats['commands_found']} "
        f"unresolved_edges={stats['unresolved_edges']} "
        f"unresolved_handlers={stats['unresolved_handlers']}"
    )
    if stats["unresolved_edges"] > 0:
        print("")
        print("Unresolved edges")
        for item in unresolved_edge_details:
            file_path = item["file_path"]
            lineno = item["lineno"]
            print(f"- {file_path}:{lineno}")
            print(f"  line: {item['source_line']}")
            print(f"  arg0_ast: {item['arg0_dump']}")
            locals_list = item["arg0_locals"]
            if locals_list:
                print(f"  locals: {', '.join(locals_list)}")
            import_hits = item["import_hits"]
            if import_hits:
                hits = ", ".join(f"{k} -> {v}" for k, v in import_hits.items())
                print(f"  import_map: {hits}")


if __name__ == "__main__":
    main()
