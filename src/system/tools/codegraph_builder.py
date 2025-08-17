# src/system/tools/codegraph_builder.py
import ast
import hashlib
import json
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from dotenv import load_dotenv
from filelock import FileLock

from shared.config_loader import load_config
from shared.logger import getLogger
from system.tools.ast_visitor import ContextAwareVisitor, FunctionCallVisitor
from system.tools.models import FunctionInfo  # <<< FIX: Import from the new models file
from system.tools.pattern_matcher import PatternMatcher

log = getLogger(__name__)


def _strip_docstrings(node):
    """Recursively remove docstring nodes from an AST tree for structural hashing."""
    if isinstance(
        node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)
    ):
        if (
            node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
        ):
            if isinstance(node.body[0].value.value, str):
                node.body = node.body[1:]
    for child_node in ast.iter_child_nodes(node):
        _strip_docstrings(child_node)
    return node


class ProjectStructureError(Exception):
    """Custom exception for when the project's root cannot be determined."""

    pass


def find_project_root(start_path: Path) -> Path:
    """Traverses upward from a starting path to find the project root, marked by 'pyproject.toml'."""
    current_path = start_path.resolve()
    while current_path != current_path.parent:
        if (current_path / "pyproject.toml").exists():
            return current_path
        current_path = current_path.parent
    raise ProjectStructureError("Could not find 'pyproject.toml'.")


# CAPABILITY: manifest_updating
class KnowledgeGraphBuilder:
    """Builds a comprehensive JSON representation of the project's code structure and relationships."""

    def __init__(self, root_path: Path, exclude_patterns: Optional[List[str]] = None):
        """Initializes the builder, loading patterns and project configuration."""
        self.root_path = root_path.resolve()
        self.src_root = self.root_path / "src"
        self.exclude_patterns = exclude_patterns or [
            "venv",
            ".venv",
            "__pycache__",
            ".git",
            "tests",
            "work",
        ]
        self.functions: Dict[str, FunctionInfo] = {}
        self.files_scanned = 0
        self.files_failed = 0
        self.cli_entry_points = self._get_cli_entry_points()
        self.patterns = self._load_patterns()
        self.domain_map = self._get_domain_map()
        self.fastapi_app_name: Optional[str] = None
        self.pattern_matcher = PatternMatcher(self.patterns, self.root_path)

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
        if not pyproject_path.exists():
            return set()
        content = pyproject_path.read_text(encoding="utf-8")
        match = re.search(r"\[tool\.poetry\.scripts\]([^\[]*)", content, re.DOTALL)
        return set(re.findall(r'=\s*"[^"]+:(\w+)"', match.group(1))) if match else set()

    def _should_exclude_path(self, path: Path) -> bool:
        """Determines if a given path should be excluded from scanning."""
        return any(p in path.parts for p in self.exclude_patterns)

    def _infer_domains_from_directory_structure(self) -> Dict[str, str]:
        """A heuristic to guess domains if source_structure.yaml is missing."""
        log.warning(
            "source_structure.yaml not found. Falling back to directory-based domain inference."
        )
        if not self.src_root.is_dir():
            log.warning("`src` directory not found. Cannot infer domains.")
            return {}

        domain_map = {}
        for item in self.src_root.iterdir():
            if item.is_dir() and not item.name.startswith(("_", ".")):
                domain_name = item.name
                domain_path = Path("src") / domain_name
                domain_map[domain_path.as_posix()] = domain_name

        log.info(
            f"   -> Inferred {len(domain_map)} domains from `src/` directory structure."
        )
        return domain_map

    def _get_domain_map(self) -> Dict[str, str]:
        """Loads the domain-to-path mapping from the constitution."""
        path = self.root_path / ".intent/knowledge/source_structure.yaml"
        data = load_config(path, "yaml")
        structure = data.get("structure")

        if not structure:
            return self._infer_domains_from_directory_structure()

        return {
            Path(e["path"]).as_posix(): e["domain"]
            for e in structure
            if "path" in e and "domain" in e
        }

    def _determine_domain(self, file_path: Path) -> str:
        """Determines the logical domain for a file path based on the longest matching prefix."""
        file_posix = file_path.as_posix()
        best = max(
            (p for p in self.domain_map if file_posix.startswith(p)),
            key=len,
            default="",
        )
        return self.domain_map.get(best, "unassigned")

    def _infer_agent_from_path(self, relative_path: Path) -> str:
        """Infers the most likely responsible agent based on keywords in the file path."""
        path = str(relative_path).lower()
        if "planner" in path:
            return "planner_agent"
        if "generator" in path:
            return "generator_agent"
        if any(x in path for x in ["validator", "guard", "audit"]):
            return "validator_agent"
        if "core" in path:
            return "core_agent"
        if "tool" in path:
            return "tooling_agent"
        return "generic_agent"

    def _parse_metadata_comment(
        self, node: ast.AST, source_lines: List[str]
    ) -> Dict[str, str]:
        """Parses the line immediately preceding a symbol definition for a '# CAPABILITY:' tag."""
        if node.lineno > 1:
            line = source_lines[node.lineno - 2].strip()
            if line.startswith("#"):
                match = re.search(r"CAPABILITY:\s*(\S+)", line, re.IGNORECASE)
                if match:
                    return {"capability": match.group(1).strip()}
        return {}

    def _get_entry_point_type(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> Optional[str]:
        """Identifies decorator or CLI-based entry points for a function."""
        for decorator in node.decorator_list:
            if (
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and isinstance(decorator.func.value, ast.Name)
                and decorator.func.value.id == self.fastapi_app_name
            ):
                return f"fastapi_route_{decorator.func.attr}"
            elif (
                isinstance(decorator, ast.Name)
                and decorator.id == "asynccontextmanager"
            ):
                return "context_manager"
        if self.fastapi_app_name and node.name == "lifespan":
            return "fastapi_lifespan"
        if node.name in self.cli_entry_points:
            return "cli_entry_point"
        return None

    def _detect_docstring(self, node: ast.AST) -> Optional[str]:
        """Detects both standard and non-standard docstrings for a node."""
        standard_doc = ast.get_docstring(node)
        if standard_doc:
            return standard_doc
        if (
            node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
        ):
            if isinstance(node.body[0].value.value, str):
                return node.body[0].value.value
        return None

    def scan_file(self, filepath: Path) -> bool:
        """Scans a single Python file, parsing its AST to extract all symbols."""
        try:
            content = filepath.read_text(encoding="utf-8")
            source_lines = content.splitlines()
            tree = ast.parse(content, filename=str(filepath))

            main_block_entries, self.fastapi_app_name = set(), None
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Assign)
                    and isinstance(node.value, ast.Call)
                    and isinstance(node.value.func, ast.Name)
                    and node.value.func.id == "FastAPI"
                    and isinstance(node.targets[0], ast.Name)
                ):
                    self.fastapi_app_name = node.targets[0].id
                elif (
                    isinstance(node, ast.If)
                    and isinstance(node.test, ast.Compare)
                    and isinstance(node.test.left, ast.Name)
                    and node.test.left.id == "__name__"
                    and isinstance(node.test.comparators[0], ast.Constant)
                    and node.test.comparators[0].value == "__main__"
                ):
                    visitor = FunctionCallVisitor()
                    visitor.visit(node)
                    main_block_entries.update(visitor.calls)
            self.cli_entry_points.update(main_block_entries)

            visitor = ContextAwareVisitor(self, filepath, source_lines)
            visitor.visit(tree)
            return True
        except UnicodeDecodeError as e:
            log.error(f"Encoding error scanning {filepath}: {e}", exc_info=True)
            return False
        except Exception as e:
            log.error(f"Error scanning {filepath}: {e}", exc_info=True)
            return False

    def _process_symbol_node(
        self,
        node: ast.AST,
        filepath: Path,
        source_lines: List[str],
        parent_key: Optional[str],
    ) -> Optional[str]:
        """Extracts and stores metadata from a single function or class AST node, including nested methods."""
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return None

        node_for_hashing = _strip_docstrings(ast.parse(ast.unparse(node)))
        structural_string = (
            ast.unparse(node_for_hashing).replace("\n", "").replace(" ", "")
        )
        structural_hash = hashlib.sha256(structural_string.encode("utf-8")).hexdigest()

        visitor = FunctionCallVisitor()
        visitor.visit(node)
        key = f"{filepath.relative_to(self.root_path).as_posix()}::{node.name}"
        doc = self._detect_docstring(node)
        domain = self._determine_domain(filepath.relative_to(self.root_path))
        is_class = isinstance(node, ast.ClassDef)

        base_classes = []
        if is_class:
            for base in node.bases:
                if isinstance(base, ast.Name):
                    base_classes.append(base.id)
                elif isinstance(base, ast.Attribute):
                    base_classes.append(base.attr)

        func_info = FunctionInfo(
            key=key,
            name=node.name,
            type=node.__class__.__name__,
            file=filepath.relative_to(self.root_path).as_posix(),
            calls=visitor.calls,
            line_number=node.lineno,
            is_async=isinstance(node, ast.AsyncFunctionDef),
            docstring=doc,
            parameters=(
                [arg.arg for arg in node.args.args] if hasattr(node, "args") else []
            ),
            entry_point_type=self._get_entry_point_type(node) if not is_class else None,
            domain=domain,
            agent=self._infer_agent_from_path(filepath.relative_to(self.root_path)),
            capability=self._parse_metadata_comment(node, source_lines).get(
                "capability", "unassigned"
            ),
            intent=(
                doc.split("\n")[0].strip()
                if doc
                else f"Provides functionality for the {domain} domain."
            ),
            last_updated=datetime.now(timezone.utc).isoformat(),
            is_class=is_class,
            base_classes=base_classes,
            parent_class_key=parent_key,
            structural_hash=structural_hash,
        )
        self.functions[key] = func_info

        if is_class:
            for child_node in node.body:
                if isinstance(child_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self._process_symbol_node(child_node, filepath, source_lines, key)

        return key

    def build(self) -> Dict[str, Any]:
        """Orchestrates the full knowledge graph generation process."""
        log.info(f"Building knowledge graph for directory: {self.src_root}")
        py_files = [
            f
            for f in self.src_root.rglob("*.py")
            if f.name != "__init__.py" and not self._should_exclude_path(f)
        ]
        log.info(f"Found {len(py_files)} Python files to scan in src/")

        for pyfile in py_files:
            if self.scan_file(pyfile):
                self.files_scanned += 1
            else:
                self.files_failed += 1

        log.info(
            f"Scanned {self.files_scanned} files ({self.files_failed} failed). Applying declarative patterns..."
        )
        self.pattern_matcher.apply_patterns(self.functions)

        serializable_functions = {
            key: asdict(
                info, dict_factory=lambda x: {k: v for (k, v) in x if v is not None}
            )
            for key, info in self.functions.items()
        }
        for data in serializable_functions.values():
            data["calls"] = sorted(list(data["calls"]))

        return {
            "schema_version": "2.0.0",
            "metadata": {
                "files_scanned": self.files_scanned,
                "total_symbols": len(self.functions),
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            },
            "symbols": serializable_functions,
        }


def main():
    """CLI entry point to run the knowledge graph builder and save the output."""
    load_dotenv()
    try:
        root = find_project_root(Path.cwd())
        builder = KnowledgeGraphBuilder(root)
        graph = builder.build()
        out_path = root / ".intent/knowledge/knowledge_graph.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with FileLock(str(out_path) + ".lock"):
            out_path.write_text(json.dumps(graph, indent=2))
        log.info(
            f"✅ Knowledge graph generated! Scanned {builder.files_scanned} files, found {len(graph['symbols'])} symbols."
        )
        log.info(f"   -> Saved to {out_path}")
    except Exception as e:
        log.error(f"An error occurred: {e}", exc_info=True)


if __name__ == "__main__":
    main()
