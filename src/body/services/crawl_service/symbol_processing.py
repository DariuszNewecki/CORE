# src/body/services/crawl_service/symbol_processing.py
# symbol_processing.py
"""handles symbol extraction and layer detection"""

from __future__ import annotations

import ast
import hashlib
import uuid
from pathlib import Path
from typing import Any


_LAYER_MAP: dict[str, str] = {
    "src/mind": "mind",
    "src/body": "body",
    "src/will": "will",
    "src/shared": "shared",
}


class _CallGraphExtractor(ast.NodeVisitor):
    """
    Extracts directed call graph edges from a Python AST.
    Produces edge dicts ready for insertion into core.symbol_calls.

    symbol_path format matches DB: src/path/to/file.py::ClassName.method_name

    Resolution cascade (applied in order until a match is found):
      1. Direct key match against symbol_index
      2. Qualname match: symbol_index key suffix after '::'
      3. self./cls. stripping + current-class qualification
      4. Module dotted path → file path conversion
         (e.g. 'will.workers.foo.Bar' → 'src/will/workers/foo.py::Bar')
      5. Short name unique match (only when exactly one symbol has that short name)
    """

    def __init__(
        self,
        rel_path: str,
        layer: str,
        symbol_index: dict[str, str],
        crawl_run_id: uuid.UUID,
    ) -> None:
        self._rel_path = rel_path
        self._layer = layer
        self._symbol_index = symbol_index
        self._crawl_run_id = str(crawl_run_id)
        self._edges: list[dict[str, Any]] = []
        self._current_caller_id: str | None = None
        self._current_class: str | None = None

        self._qualname_index: dict[str, str] = {}
        _shortname_bucket: dict[str, list[str]] = {}

        for symbol_path, symbol_id in symbol_index.items():
            if "::" not in symbol_path:
                continue
            qualname = symbol_path.split("::", 1)[1]
            self._qualname_index[qualname] = symbol_id
            short = qualname.split(".")[-1]
            _shortname_bucket.setdefault(short, []).append(symbol_id)

        self._shortname_index: dict[str, str] = {
            k: v[0] for k, v in _shortname_bucket.items() if len(v) == 1
        }

    # ID: 6b2f1fc9-9666-44db-a3e1-407dc81e2a39
    def extract(self, tree: ast.AST) -> list[dict[str, Any]]:
        self.visit(tree)
        return self._edges

    # ID: 02eaa803-3c00-4aa3-b2e5-dbaced1a91a2
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if self._current_class:
            qualname = f"{self._current_class}.{node.name}"
        else:
            qualname = node.name
        symbol_path = f"{self._rel_path}::{qualname}"
        self._current_caller_id = self._symbol_index.get(symbol_path)
        self.generic_visit(node)
        self._current_caller_id = None

    visit_AsyncFunctionDef = visit_FunctionDef

    # ID: 216190a2-ca25-4659-9cac-7659d3fefef4
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        prev_class = self._current_class
        self._current_class = node.name
        symbol_path = f"{self._rel_path}::{node.name}"
        caller_id = self._symbol_index.get(symbol_path)
        for base in node.bases:
            callee_raw = ast.unparse(base)
            self._add_edge(
                callee_raw=callee_raw,
                edge_kind="inheritance",
                line_number=node.lineno,
                caller_id=caller_id,
            )
        self.generic_visit(node)
        self._current_class = prev_class

    # ID: 09f061e2-059f-4fce-8232-1c10ff4df527
    def visit_Call(self, node: ast.Call) -> None:
        if self._current_caller_id is None:
            self.generic_visit(node)
            return
        callee_raw = ast.unparse(node.func)
        self._add_edge(
            callee_raw=callee_raw,
            edge_kind="direct_call",
            line_number=node.lineno,
        )
        self.generic_visit(node)

    # ID: b15b99d6-420f-49b9-8cbf-c5a83f8f6700
    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._add_edge(
                callee_raw=alias.name,
                edge_kind="import",
                line_number=node.lineno,
            )

    # ID: 855c7b0d-8fe4-4fd5-a7f9-c694ff9adce3
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        for alias in node.names:
            callee_raw = f"{module}.{alias.name}" if module else alias.name
            self._add_edge(
                callee_raw=callee_raw,
                edge_kind="import",
                line_number=node.lineno,
            )

    def _resolve_callee_id(self, callee_raw: str) -> str | None:
        """Multi-strategy callee resolution cascade."""
        hit = self._symbol_index.get(callee_raw)
        if hit:
            return hit

        hit = self._qualname_index.get(callee_raw)
        if hit:
            return hit

        if self._current_class and callee_raw.startswith(("self.", "cls.")):
            stripped = callee_raw.split(".", 1)[1]
            qualified = f"{self._current_class}.{stripped}"
            hit = self._qualname_index.get(qualified)
            if hit:
                return hit
            hit = self._qualname_index.get(stripped)
            if hit:
                return hit

        if "." in callee_raw:
            parts = callee_raw.split(".")
            for split in range(len(parts) - 1, 0, -1):
                module_path = "src/" + "/".join(parts[:split]) + ".py"
                qualname = ".".join(parts[split:])
                candidate = f"{module_path}::{qualname}"
                hit = self._symbol_index.get(candidate)
                if hit:
                    return hit
                candidate_no_src = "/".join(parts[:split]) + ".py::" + qualname
                hit = self._symbol_index.get(candidate_no_src)
                if hit:
                    return hit

        short = callee_raw.split(".")[-1]
        hit = self._shortname_index.get(short)
        if hit:
            return hit

        return None

    def _add_edge(
        self,
        callee_raw: str,
        edge_kind: str,
        line_number: int | None,
        caller_id: str | None = None,
    ) -> None:
        resolved_caller_id = caller_id or self._current_caller_id
        if resolved_caller_id is None:
            return

        callee_id = self._resolve_callee_id(callee_raw)
        caller_layer = self._layer
        callee_layer = _detect_layer_from_symbol(callee_raw)
        is_cross_layer = (
            caller_layer != callee_layer
            and callee_layer != "unknown"
            and caller_layer != "unknown"
        )
        is_external = not callee_raw.startswith(
            ("src.", "will.", "body.", "mind.", "shared.")
        )

        self._edges.append(
            {
                "caller_id": resolved_caller_id,
                "callee_id": callee_id,
                "callee_raw": callee_raw[:500],
                "edge_kind": edge_kind,
                "file_path": self._rel_path,
                "line_number": line_number,
                "is_cross_layer": is_cross_layer,
                "is_external": is_external,
                "crawl_run_id": self._crawl_run_id,
            }
        )


def _detect_layer(rel_path: str) -> str:
    """Detect architectural layer from repo-relative file path."""
    for prefix, layer in _LAYER_MAP.items():
        if rel_path.startswith(prefix):
            return layer
    return "unknown"


def _detect_layer_from_symbol(symbol: str) -> str:
    """Detect layer from a dotted symbol/module name."""
    for prefix, layer in {
        "mind.": "mind",
        "body.": "body",
        "will.": "will",
        "shared.": "shared",
    }.items():
        if symbol.startswith(prefix):
            return layer
    return "unknown"


def _find_symbol_references(
    content: str,
    symbol_index: dict[str, str],
    rel_path: str,
    artifact_type: str,
) -> list[dict[str, Any]]:
    """
    Scan file text for mentions of known symbol qualnames.
    Returns link dicts ready for core.artifact_symbol_links insertion.
    """
    link_kind_map = {
        "doc": "documents",
        "test": "tests",
        "intent": "governs",
        "infra": "configures",
        "prompt": "references",
        "report": "references",
    }
    link_kind = link_kind_map.get(artifact_type, "references")
    links: list[dict[str, Any]] = []
    seen: set[str] = set()

    for symbol_path, symbol_id in symbol_index.items():
        qualname = symbol_path.split(":")[-1] if ":" in symbol_path else symbol_path
        if len(qualname) < 4:
            continue
        if qualname in content and symbol_id not in seen:
            seen.add(symbol_id)
            links.append(
                {
                    "symbol_id": symbol_id,
                    "link_kind": link_kind,
                    "confidence": 0.8,
                    "source": "name_match",
                }
            )
    return links


def _sha256(path: Path) -> str:
    """Compute SHA256 hex digest of a file."""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()
