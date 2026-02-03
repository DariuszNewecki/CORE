# src/shared/infrastructure/context/builder.py

"""
ContextBuilder - Sensory-aware context assembly.

CONSTITUTIONAL AUTHORITY: Infrastructure (coordination)

ALIGNS WITH PILLAR I (Octopus):
Provides a unified sensation of "Shadow Truth" (in-flight changes) vs
"Historical Truth" (database).

HEALED (V2.6.7):
- Content Extraction: Always attempts to read from workspace first.
- Context Consistency: Prevents the AI from being blind to its own proposed code.
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

    # ID: 9145ae00-921d-4006-9032-039b5d7a6f38
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._add_symbol(node)
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    # ID: a9f6d953-64b0-45c3-8437-8fcfca912688
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._add_symbol(node)
        self.generic_visit(node)

    # ID: aa0b2883-6101-440d-a4b4-f046d0c4a7aa
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


# ID: d4e5f6a7-b8c9-0d1e-2f3a-4b5c6d7e8f9a
class _GraphExplorer:
    """Specialist in traversing the Knowledge Graph to find related logic."""

    @staticmethod
    # ID: 155cfe19-0d30-4cee-9148-fae389881086
    def traverse(graph: dict, seeds: list[dict], depth: int, limit: int) -> set[str]:
        all_symbols = graph.get("symbols", {})
        related = set()
        queue = set()
        for s in seeds:
            path = s.get("metadata", {}).get("symbol_path") or s.get("symbol_path")
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

    # ID: be34f105-e983-4c0e-9e20-79603db377a3
    async def build_for_task(self, task_spec: dict[str, Any]) -> dict[str, Any]:
        """Main entry point for building a task-specific packet."""
        start = datetime.now(UTC)

        # 1. SENSATION: Load the graph (Shadow if workspace exists, else Historical)
        graph = await self._load_truth()
        packet = self._init_packet(task_spec)

        # 2. COLLECTION: Extract items
        items = await self._collect_items(task_spec, graph, packet["constraints"])

        # 3. FINALIZATION
        packet["context"] = self._finalize_items(items, packet["constraints"])
        packet["provenance"]["build_stats"] = {
            "duration_ms": int((datetime.now(UTC) - start).total_seconds() * 1000),
            "tokens_total": sum(i.get("tokens_est", 0) for i in packet["context"]),
        }
        return packet

    async def _load_truth(self) -> dict:
        """Sensation: Prefers Shadow Graph if limb is in motion."""
        if self.workspace:
            return KnowledgeGraphBuilder(
                settings.REPO_PATH, workspace=self.workspace
            ).build()
        return await KnowledgeService(settings.REPO_PATH).get_graph()

    async def _collect_items(self, spec: dict, graph: dict, limits: dict) -> list[dict]:
        """Collects context items. Prioritizes Workspace over DB if active."""
        items = []

        if self.workspace:
            logger.debug("Builder: Seeding context from Shadow Graph")
            include_filters = spec.get("scope", {}).get("include", [])
            for key, data in graph.get("symbols", {}).items():
                if any(f in key for f in include_filters) or not include_filters:
                    if len(items) < (limits["max_items"] // 2):
                        items.append(self._format_item(data))
        else:
            if self.db:
                items.extend(
                    await self.db.fetch_symbols_for_scope(
                        spec.get("scope", {}), limits["max_items"] // 2
                    )
                )

        if self.vectors and spec.get("summary"):
            items.extend(await self.vectors.search_similar(spec["summary"], top_k=3))

        depth = spec.get("scope", {}).get("traversal_depth", 0)
        if depth > 0:
            related_keys = _GraphExplorer.traverse(
                graph, items, depth, limits["max_items"]
            )
            for k in list(related_keys):
                if sym := graph["symbols"].get(k):
                    items.append(self._format_item(sym))

        return items

    # ID: HEALED_format_item
    def _format_item(self, symbol_data: dict) -> dict:
        """Translates a Graph Symbol into a Context Item."""
        path = symbol_data.get("file_path", "")
        name = symbol_data.get("name", "")
        content, sig = None, str(symbol_data.get("parameters", []))

        try:
            # HEALED: Prioritize reading from virtual workspace sensation
            if self.workspace and self.workspace.exists(path):
                src = self.workspace.read_text(path)
            else:
                src = (settings.REPO_PATH / path).read_text(encoding="utf-8")

            tracker = ScopeTracker(src)
            tracker.visit(ast.parse(src))
            for s in tracker.symbols:
                if s["name"] == name:
                    content, sig = s["code"], s["signature"]
                    break
        except Exception as e:
            logger.debug("Content extraction failed for %s in %s: %s", name, path, e)

        return {
            "name": name,
            "path": path,
            "item_type": "code" if content else "symbol",
            "content": content,
            "signature": sig,
            "summary": symbol_data.get("intent", ""),
            "source": "shadow_sensation" if self.workspace else "historical_record",
            "symbol_path": symbol_data.get("symbol_path"),
        }

    def _init_packet(self, spec: dict) -> dict:
        return {
            "header": {
                "packet_id": str(uuid.uuid4()),
                "task_id": spec["task_id"],
                "created_at": datetime.now(UTC).isoformat(),
                "builder_version": "0.2.2",
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
