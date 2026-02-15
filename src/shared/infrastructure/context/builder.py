# src/shared/infrastructure/context/builder.py

"""
ContextBuilder - Sensory-aware context assembly.

CONSTITUTIONAL AUTHORITY: Infrastructure (coordination)

ALIGNS WITH PILLAR I (Octopus):
Provides a unified sensation of "Shadow Truth" (in-flight changes) vs
"Historical Truth" (database).

HEALED (V2.7.0):
- Fixed Vector Result Blindness: Now extracts code for semantic search hits.
- Hardened Sensation: Handles symbol_path keys (::) correctly during extraction.
- Preserved GraphExplorer: Retains advanced relationship traversal logic.
"""

from __future__ import annotations

import ast
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from features.introspection.knowledge_graph_service import KnowledgeGraphBuilder
from shared.config import settings
from shared.infrastructure.knowledge.knowledge_service import KnowledgeService
from shared.logger import getLogger

from .serializers import ContextSerializer


if TYPE_CHECKING:
    from shared.infrastructure.context.limb_workspace import LimbWorkspace

    from .providers.ast import ASTProvider
    from .providers.db import DBProvider
    from .providers.vectors import VectorProvider

logger = getLogger(__name__)


# ID: 7ac392a5-996c-45e5-ad32-e31ce9911f14
class ScopeTracker(ast.NodeVisitor):
    """AST visitor that collects symbol metadata and signatures."""

    def __init__(self, source: str) -> None:
        self.source = source
        self.stack: list[str] = []
        self.symbols: list[dict[str, Any]] = []

    # ID: 74d2971d-9919-4fa2-98e3-0231ee5a5a7d
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._add_symbol(node)
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    # ID: 00cca3c5-ecac-4fd2-b26e-724720994f7d
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._add_symbol(node)
        self.generic_visit(node)

    # ID: 1f850daa-a3c6-4eea-a4e2-44282126ae71
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._add_symbol(node)
        self.generic_visit(node)

    def _add_symbol(self, node: Any) -> None:
        qualname = f"{'.'.join(self.stack)}.{node.name}" if self.stack else node.name
        try:
            lines = self.source.splitlines()
            end = getattr(node, "end_lineno", node.lineno) or node.lineno
            code = "\n".join(lines[node.lineno - 1 : end])
            sig = code.split("\n")[0]
        except Exception as e:
            logger.debug("Symbol extraction failed for %s: %s", node.name, e)
            sig, code = f"def {node.name}(...)", "# Extraction failed"

        self.symbols.append(
            {
                "name": node.name,
                "qualname": qualname,
                "signature": sig,
                "code": code,
                "docstring": ast.get_docstring(node) or "",
            }
        )


# ID: b0b96134-dd20-4c4d-92a6-2b34b033d9ae
class _GraphExplorer:
    """Specialist in traversing the Knowledge Graph to find related logic."""

    @staticmethod
    # ID: 54bc0352-afce-4d61-8d47-c35366f138e5
    def traverse(graph: dict, seeds: list[dict], depth: int, limit: int) -> set[str]:
        all_symbols = graph.get("symbols", {})
        related = set()
        queue = set()
        for s in seeds:
            # Check multiple possible key locations
            path = (
                s.get("metadata", {}).get("symbol_path")
                or s.get("symbol_path")
                or s.get("name")
            )
            if path:
                queue.add(path)

        for _ in range(depth):
            if not queue or len(related) >= limit:
                break
            next_q = set()
            for key in queue:
                data = all_symbols.get(key, {})
                for callee in data.get("calls", []):
                    if callee not in related:
                        related.add(callee)
                        next_q.add(callee)
            queue = next_q
        return related


# ID: e90e2005-1f52-47e2-a456-46bdd1532a44
class ContextBuilder:
    """
    Assembles governed ContextPackages by merging historical and future truth.
    """

    def __init__(
        self,
        db_provider: DBProvider,
        vector_provider: VectorProvider,
        ast_provider: ASTProvider,
        config: dict,
        workspace: LimbWorkspace | None = None,
    ):
        self.db = db_provider
        self.vectors = vector_provider
        self.ast = ast_provider
        self.config = config or {}
        self.workspace = workspace

    # ID: b5b19f31-7c4c-4e1f-a71c-788fa02cb1f5
    async def build_for_task(self, task_spec: dict[str, Any]) -> dict[str, Any]:
        """Main entry point for building a task-specific packet."""
        start = datetime.now(UTC)

        graph = await self._load_truth()
        packet = self._init_packet(task_spec)

        items = await self._collect_items(task_spec, graph, packet["constraints"])

        packet["context"] = self._finalize_items(items, packet["constraints"])
        packet["provenance"]["build_stats"] = {
            "duration_ms": int((datetime.now(UTC) - start).total_seconds() * 1000),
            "tokens_total": sum(i.get("tokens_est", 0) for i in packet["context"]),
        }
        return packet

    async def _load_truth(self) -> dict:
        if self.workspace:
            return KnowledgeGraphBuilder(
                settings.REPO_PATH, workspace=self.workspace
            ).build()
        return await KnowledgeService(settings.REPO_PATH).get_graph()

    async def _collect_items(self, spec: dict, graph: dict, limits: dict) -> list[dict]:
        items = []

        # 1. Handle Shadow Truth (Workspace)
        if self.workspace:
            include_filters = spec.get("scope", {}).get("include", [])
            for key, data in graph.get("symbols", {}).items():
                if any(f in key for f in include_filters) or not include_filters:
                    if len(items) < (limits["max_items"] // 2):
                        items.append(self._format_item(data))

        # 2. Handle Semantic Search (HEALED: Now extracts code)
        if self.vectors and spec.get("summary"):
            vector_results = await self.vectors.search_similar(spec["summary"], top_k=5)
            for v_item in vector_results:
                items.append(self._extract_code_for_item(v_item))

        # 3. Handle Historical Truth (Database)
        if not self.workspace and self.db:
            db_results = await self.db.fetch_symbols_for_scope(
                spec.get("scope", {}), limits["max_items"] // 2
            )
            for db_item in db_results:
                items.append(self._extract_code_for_item(db_item))

        # 4. Handle Relationship Traversal (Graph)
        depth = spec.get("scope", {}).get("traversal_depth", 0)
        if depth > 0:
            related_keys = _GraphExplorer.traverse(
                graph, items, depth, limits["max_items"]
            )
            for k in list(related_keys):
                if sym := graph.get("symbols", {}).get(k):
                    items.append(self._format_item(sym))

        return items

    def _format_item(self, symbol_data: dict) -> dict:
        """Translates a Graph Symbol into a Context Item."""
        path = symbol_data.get("file_path", "")
        name = symbol_data.get("name", "")

        # Build the initial item shell
        item = {
            "name": name,
            "path": path,
            "item_type": "symbol",
            "content": None,
            "signature": str(symbol_data.get("parameters", [])),
            "summary": symbol_data.get("intent", ""),
            "source": "shadow_sensation" if self.workspace else "historical_record",
            "symbol_path": symbol_data.get("symbol_path"),
        }

        # Immediately try to upgrade to "code" item type
        return self._extract_code_for_item(item)

    def _extract_code_for_item(self, item: dict) -> dict:
        """THE SENSATION STEP: Read actual code from the filesystem."""
        path = item.get("path", "")
        # Name might be 'Symbol' or 'file.py::Symbol'
        name_raw = item.get("name", "")
        target_name = name_raw.split("::")[-1] if "::" in name_raw else name_raw

        if not path or not target_name:
            return item

        try:
            if self.workspace and self.workspace.exists(path):
                src = self.workspace.read_text(path)
            else:
                abs_path = settings.REPO_PATH / path
                if not abs_path.exists():
                    return item
                src = abs_path.read_text(encoding="utf-8")

            tracker = ScopeTracker(src)
            tracker.visit(ast.parse(src))
            for s in tracker.symbols:
                if s["name"] == target_name or s["qualname"] == target_name:
                    item["content"] = s["code"]
                    item["signature"] = s["signature"]
                    item["item_type"] = "code"
                    break
        except Exception as e:
            logger.debug("Content extraction failed for %s: %s", target_name, e)

        return item

    def _init_packet(self, spec: dict) -> dict:
        return {
            "header": {
                "packet_id": str(uuid.uuid4()),
                "task_id": spec.get("task_id", "manual"),
                "task_type": spec.get("task_type", "unknown"),
                "created_at": datetime.now(UTC).isoformat(),
                "builder_version": "0.2.2",
                "privacy": "local_only",
                "mode": "SHADOW" if self.workspace else "HISTORICAL",
            },
            "constraints": {
                "max_tokens": spec.get("constraints", {}).get("max_tokens", 50000),
                "max_items": spec.get("constraints", {}).get("max_items", 30),
            },
            "provenance": {"cache_key": ContextSerializer.compute_cache_key(spec)},
            "context": [],
        }

    def _finalize_items(self, items: list[dict], limits: dict) -> list[dict]:
        unique, seen, total_tokens = [], set(), 0
        for it in items:
            key = (it["name"], it["path"])
            if key in seen or len(unique) >= limits["max_items"]:
                continue
            tokens = ContextSerializer.estimate_tokens(
                (it.get("content") or "") + (it.get("summary") or "")
            )
            if total_tokens + tokens > limits["max_tokens"]:
                break
            it["tokens_est"] = tokens
            unique.append(it)
            seen.add(key)
            total_tokens += tokens
        return unique
