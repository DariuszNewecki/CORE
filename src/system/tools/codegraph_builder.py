# src/system/tools/codegraph_builder.py
import ast
import json
import re
from pathlib import Path
from typing import Dict, Set, Optional, List, Any
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone

from shared.config_loader import load_config
from shared.logger import getLogger

log = getLogger(__name__)

@dataclass
class FunctionInfo:
    """A data structure holding all analyzed information about a single symbol (function or class)."""
    key: str
    name: str
    type: str
    file: str
    domain: str
    agent: str
    capability: str
    intent: str
    docstring: Optional[str]
    calls: Set[str] = field(default_factory=set)
    line_number: int = 0
    is_async: bool = False
    parameters: List[str] = field(default_factory=list)
    entry_point_type: Optional[str] = None
    last_updated: str = ""
    is_class: bool = False
    base_classes: List[str] = field(default_factory=list)
    entry_point_justification: Optional[str] = None
    parent_class_key: Optional[str] = None

class ProjectStructureError(Exception):
    """Custom exception for when the project's root cannot be determined."""
    pass

def find_project_root(start_path: Path) -> Path:
    """
    Traverses upward from a starting path to find the project root, marked by 'pyproject.toml'.
    """
    current_path = start_path.resolve()
    while current_path != current_path.parent:
        if (current_path / "pyproject.toml").exists():
            return current_path
        current_path = current_path.parent
    raise ProjectStructureError("Could not find 'pyproject.toml'.")

class FunctionCallVisitor(ast.NodeVisitor):
    """An AST visitor that collects the names of all functions being called within a node."""
    def __init__(self):
        """Initializes the visitor with an empty set to store call names."""
        self.calls: Set[str] = set()

    def visit_Call(self, node: ast.Call):
        """Extracts the function name from a Call node."""
        if isinstance(node.func, ast.Name): self.calls.add(node.func.id)
        elif isinstance(node.func, ast.Attribute): self.calls.add(node.func.attr)
        self.generic_visit(node)

# CAPABILITY: manifest_updating
class KnowledgeGraphBuilder:
    """Builds a comprehensive JSON representation of the project's code structure and relationships."""

    class ContextAwareVisitor(ast.NodeVisitor):
        """A stateful AST visitor that understands class context for methods."""
        def __init__(self, builder, filepath: Path, source_lines: List[str]):
            """Initializes the context-aware visitor."""
            self.builder = builder
            self.filepath = filepath
            self.source_lines = source_lines
            self.current_class_key: Optional[str] = None

        def visit_ClassDef(self, node: ast.ClassDef):
            """Processes a class definition, setting the context for its methods."""
            class_key = self.builder._process_symbol_node(node, self.filepath, self.source_lines, None)
            outer_class_key = self.current_class_key
            self.current_class_key = class_key
            self.generic_visit(node)
            self.current_class_key = outer_class_key

        def visit_FunctionDef(self, node: ast.FunctionDef):
            """Processes a standard function or method within its class context."""
            self.builder._process_symbol_node(node, self.filepath, self.source_lines, self.current_class_key)
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
            """Processes an async function or method within its class context."""
            self.builder._process_symbol_node(node, self.filepath, self.source_lines, self.current_class_key)
            self.generic_visit(node)

    def __init__(self, root_path: Path, exclude_patterns: Optional[List[str]] = None):
        """Initializes the builder, loading patterns and project configuration."""
        self.root_path = root_path.resolve()
        self.src_root = self.root_path / "src"
        self.exclude_patterns = exclude_patterns or ["venv", ".venv", "__pycache__", ".git", "tests"]
        self.functions: Dict[str, FunctionInfo] = {}
        self.files_scanned = 0
        self.files_failed = 0
        self.cli_entry_points = self._get_cli_entry_points()
        self.patterns = self._load_patterns()
        self.domain_map = self._get_domain_map()
        self.fastapi_app_name: Optional[str] = None

    def _load_patterns(self) -> List[Dict]:
        """Loads entry point detection patterns from the intent file."""
        patterns_path = self.root_path / ".intent/knowledge/entry_point_patterns.yaml"
        if not patterns_path.exists():
            log.warning("entry_point_patterns.yaml not found.")
            return []
        return load_config(patterns_path, "yaml").get("patterns", [])

    def _get_cli_entry_points(self) -> Set[str]:
        """Parses pyproject.toml to find declared command-line entry points."""
        pyproject_path = self.root_path / "pyproject.toml"
        if not pyproject_path.exists(): return set()
        content = pyproject_path.read_text(encoding="utf-8")
        match = re.search(r"\[tool\.poetry\.scripts\]([^\[]*)", content, re.DOTALL)
        return set(re.findall(r'=\s*"[^"]+:(\w+)"', match.group(1))) if match else set()

    def _should_exclude_path(self, path: Path) -> bool:
        """Determines if a given path should be excluded from scanning."""
        return any(p in path.parts for p in self.exclude_patterns)

    def _get_domain_map(self) -> Dict[str, str]:
        """Loads the domain-to-path mapping from the source structure intent file."""
        path = self.root_path / ".intent/knowledge/source_structure.yaml"
        data = load_config(path, "yaml")
        return {Path(e["path"]).as_posix(): e["domain"] for e in data.get("structure", []) if "path" in e and "domain" in e}

    def _determine_domain(self, file_path: Path) -> str:
        """Determines the logical domain for a file path based on the longest matching prefix."""
        file_posix = file_path.as_posix()
        best = max((p for p in self.domain_map if file_posix.startswith(p)), key=len, default="")
        return self.domain_map.get(best, "unassigned")

    def _infer_agent_from_path(self, relative_path: Path) -> str:
        """Infers the most likely responsible agent based on keywords in the file path."""
        path = str(relative_path).lower()
        if "planner" in path: return "planner_agent"
        if "generator" in path: return "generator_agent"
        if any(x in path for x in ["validator", "guard", "audit"]): return "validator_agent"
        if "core" in path: return "core_agent"
        if "tool" in path: return "tooling_agent"
        return "generic_agent"

    def _parse_metadata_comment(self, node: ast.AST, source_lines: List[str]) -> Dict[str, str]:
        """Parses the line immediately preceding a symbol definition for a '# CAPABILITY:' tag."""
        if node.lineno > 1:
            line = source_lines[node.lineno - 2].strip()
            if line.startswith('#'):
                match = re.search(r'CAPABILITY:\s*(\S+)', line, re.IGNORECASE)
                if match: return {'capability': match.group(1).strip()}
        return {}

    def _get_entry_point_type(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> Optional[str]:
        """Identifies decorator or CLI-based entry points for a function."""
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute) and isinstance(decorator.func.value, ast.Name) and decorator.func.value.id == self.fastapi_app_name:
                return f"fastapi_route_{decorator.func.attr}"
            elif isinstance(decorator, ast.Name) and decorator.id == "asynccontextmanager":
                return "context_manager"
        if self.fastapi_app_name and node.name == "lifespan": return "fastapi_lifespan"
        if node.name in self.cli_entry_points: return "cli_entry_point"
        return None

    def scan_file(self, filepath: Path) -> bool:
        """Scans a single Python file, parsing its AST to extract all symbols."""
        try:
            content = filepath.read_text(encoding="utf-8")
            source_lines = content.splitlines()
            tree = ast.parse(content, filename=str(filepath))
            
            main_block_entries, self.fastapi_app_name = set(), None
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == 'FastAPI' and isinstance(node.targets[0], ast.Name):
                    self.fastapi_app_name = node.targets[0].id
                elif isinstance(node, ast.If) and isinstance(node.test, ast.Compare) and isinstance(node.test.left, ast.Name) and node.test.left.id == '__name__' and isinstance(node.test.comparators[0], ast.Constant) and node.test.comparators[0].value == '__main__':
                    visitor = FunctionCallVisitor(); visitor.visit(node); main_block_entries.update(visitor.calls)
            self.cli_entry_points.update(main_block_entries)

            visitor = self.ContextAwareVisitor(self, filepath, source_lines)
            visitor.visit(tree)
            return True
        except Exception as e:
            log.error(f"Error scanning {filepath}: {e}", exc_info=False)
            return False

    def _process_symbol_node(self, node: ast.AST, filepath: Path, source_lines: List[str], parent_key: Optional[str]) -> Optional[str]:
        """Extracts and stores metadata from a single function or class AST node."""
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)): return None
        
        visitor = FunctionCallVisitor(); visitor.visit(node)
        key = f"{filepath.relative_to(self.root_path).as_posix()}::{node.name}"
        doc = ast.get_docstring(node) or ""
        domain = self._determine_domain(filepath.relative_to(self.root_path))
        is_class = isinstance(node, ast.ClassDef)

        base_classes = []
        if is_class:
            for base in node.bases:
                if isinstance(base, ast.Name): base_classes.append(base.id)
                elif isinstance(base, ast.Attribute): base_classes.append(base.attr)
        
        func_info = FunctionInfo(
            key=key, name=node.name, type=node.__class__.__name__, file=filepath.relative_to(self.root_path).as_posix(),
            calls=visitor.calls, line_number=node.lineno, is_async=isinstance(node, ast.AsyncFunctionDef),
            docstring=doc, parameters=[arg.arg for arg in node.args.args] if hasattr(node, 'args') else [],
            entry_point_type=self._get_entry_point_type(node) if not is_class else None,
            domain=domain, agent=self._infer_agent_from_path(filepath.relative_to(self.root_path)),
            capability=self._parse_metadata_comment(node, source_lines).get("capability", "unassigned"),
            intent=doc.split('\n')[0].strip() or f"Provides functionality for the {domain} domain.",
            last_updated=datetime.now(timezone.utc).isoformat(), is_class=is_class,
            base_classes=base_classes, parent_class_key=parent_key
        )
        self.functions[key] = func_info
        return key

    def _apply_entry_point_patterns(self):
        """Applies declarative patterns to identify non-obvious entry points."""
        all_base_classes = {base for info in self.functions.values() for base in info.base_classes}
        for info in self.functions.values():
            if info.entry_point_type: continue
            for pattern in self.patterns:
                rules, is_match = pattern.get("match", {}), True
                
                if rules.get("has_capability_tag") and info.capability == "unassigned": is_match = False
                if rules.get("is_base_class") and (not info.is_class or info.name not in all_base_classes): is_match = False
                if "name_regex" in rules and not re.match(rules["name_regex"], info.name): is_match = False
                
                if "base_class_includes" in rules:
                    parent_bases = info.base_classes
                    if info.parent_class_key and info.parent_class_key in self.functions:
                        parent_bases.extend(self.functions[info.parent_class_key].base_classes)
                    if not any(b == rules["base_class_includes"] for b in parent_bases): is_match = False

                if is_match:
                    info.entry_point_type, info.entry_point_justification = pattern["entry_point_type"], pattern["name"]
                    break

    def build(self) -> Dict[str, Any]:
        """Orchestrates the full knowledge graph generation process."""
        log.info(f"Building knowledge graph for directory: {self.src_root}")
        py_files = [f for f in self.src_root.rglob("*.py") if f.name != "__init__.py" and not self._should_exclude_path(f)]
        log.info(f"Found {len(py_files)} Python files to scan in src/")
        
        for pyfile in py_files:
            if self.scan_file(pyfile): self.files_scanned += 1
            else: self.files_failed += 1
        
        log.info(f"Scanned {self.files_scanned} files ({self.files_failed} failed). Applying declarative patterns...")
        self._apply_entry_point_patterns()

        serializable_functions = {key: asdict(info, dict_factory=lambda x: {k: v for (k, v) in x if v is not None}) for key, info in self.functions.items()}
        for data in serializable_functions.values(): data["calls"] = sorted(list(data["calls"]))
        
        return {
            "schema_version": "2.0.0",
            "metadata": {"files_scanned": self.files_scanned, "total_symbols": len(self.functions), "timestamp_utc": datetime.now(timezone.utc).isoformat()},
            "symbols": serializable_functions
        }

def main():
    """CLI entry point to run the knowledge graph builder and save the output."""
    try:
        root = find_project_root(Path.cwd())
        builder = KnowledgeGraphBuilder(root)
        graph = builder.build()
        out_path = root / ".intent/knowledge/knowledge_graph.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(graph, indent=2))
        log.info(f"✅ Knowledge graph generated! Scanned {builder.files_scanned} files, found {len(graph['symbols'])} symbols.")
        log.info(f"   -> Saved to {out_path}")
    except Exception as e:
        log.error(f"An error occurred: {e}", exc_info=True)

if __name__ == "__main__":
    main()